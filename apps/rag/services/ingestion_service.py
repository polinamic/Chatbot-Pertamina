"""
ingestion_service.py — Multi-Format Chunking Strategy

FORMAT YANG DIDUKUNG:
=====================

  [FORMAT 1] KB_Troubleshoots — YAML Frontmatter + Markdown
  ----------------------------------------------------------
  Marker  : konten mengandung 'type: TROUBLESHOOT' atau blok '---\\ntype:'
  Contoh  :
    ---
    type: TROUBLESHOOT
    title: Akun terkunci...
    keywords: akun, password, ...
    category: IT_PROBLEM
    ---
    ## Deskripsi Masalah
    ...
    ## Langkah Solusi
    1. ...

  [FORMAT 2] Eskalasi_MySSC — Custom Flat dengan Group Header
  -----------------------------------------------------------
  Marker  : konten mengandung '\\nGRUP ' dan 'NAMA FORM:'
  Contoh  :
    ==================================================
    GRUP 1: ORDER_LINK (Form Pengadaan / Permintaan)
    ==================================================

    ---
    NAMA FORM: Acces Control Device
    TRIGGER KEYWORD: access, control, ...
    PANDUAN TIKET: Untuk menghubungi tim IT...
    Link: https://...
    ---

  [FORMAT 3] Eskalasi_Incident — Custom Flat Sederhana (tanpa Grup)
  -----------------------------------------------------------------
  Marker  : konten mengandung 'NAMA FORM:' tetapi TIDAK mengandung '\\nGRUP '
  Contoh  :
    ---
    NAMA FORM: Incident
    TRIGGER KEYWORD: error, rusak, ...
    PANDUAN TIKET: Untuk menghubungi tim IT...
    Link: https://...
    ---

STRATEGI CHUNKING:
==================
- KB_Troubleshoots → markdown_aware_chunking()    → 1 chunk per entri KB
- Eskalasi_MySSC   → eskalasi_aware_chunking()    → 1 chunk per NAMA FORM,
                                                     dengan prefix GRUP sebagai konteks
- Eskalasi_Incident→ eskalasi_aware_chunking()    → 1 chunk per NAMA FORM
                                                     (tanpa prefix GRUP)

Trade-off prefix repetition pada eskalasi:
  Menyertakan nama GRUP di setiap chunk menambah token embedding,
  tetapi memastikan retrieval tidak kehilangan konteks "ini form pengadaan"
  vs "ini form insiden" ketika user query ambigu.
"""

import re
import logging
from apps.rag.models import DocumentChunk
from apps.rag.apps import get_embedding_service
from apps.rag.services.metadata_manager import extract_metadata_from_chunk

logger = logging.getLogger(__name__)

# ============================================================
# KONFIGURASI CHUNKING
# ============================================================

# (Batasan karakter per chunk dihapus agar 1 Form/Panduan menjadi 1 Vektor utuh)
# ============================================================
# FORMAT DETECTION
# ============================================================

def detect_document_format(content: str) -> str:
    """
    Deteksi format dokumen berdasarkan marker unik di konten.

    Returns:
        'kb_markdown'       → KB_Troubleshoots format (YAML frontmatter)
        'eskalasi_myssc'    → Eskalasi_MySSC format (GRUP + NAMA FORM)
        'eskalasi_incident' → Eskalasi_Incident format (NAMA FORM tanpa GRUP)
        'unknown'           → Fallback ke markdown_aware_chunking
    """
    # Marker paling spesifik dicek lebih dulu (urutan penting)
    if re.search(r'^type:\s*TROUBLESHOOT', content, re.MULTILINE):
        return 'kb_markdown'

    has_grup = bool(re.search(r'\nGRUP\s+\d+\s*:', content))
    has_nama_form = 'NAMA FORM:' in content

    if has_nama_form and has_grup:
        return 'eskalasi_myssc'

    if has_nama_form and not has_grup:
        return 'eskalasi_incident'

    # Fallback: coba markdown-aware chunking
    return 'unknown'


# ============================================================
# CHUNKER 1: KB_TROUBLESHOOTS — Markdown + YAML Frontmatter
# ============================================================

def markdown_aware_chunking(content: str) -> list[str]:
    """
    Chunking untuk KB_Troubleshoots.txt (YAML frontmatter + Markdown body).

    Strategi:
    - Split menggunakan positive lookahead pada batas frontmatter '---'
    - Setiap entri (frontmatter + body) = 1 chunk
    - Jika entri > MAX_CHUNK_SIZE, pecah body-nya dengan
      prefix repetition (frontmatter tetap ada di setiap sub-chunk)
    """
    chunks = []
    content = content.replace('\r\n', '\n').strip()

    # Split HANYA pada pembuka frontmatter baru: baris '---' yang diikuti 'type:'
    # Ini mencegah split di penutup frontmatter (---) yang memisahkan
    # frontmatter dari body-nya (masalah orphan chunks).
    raw_entries = re.split(r'(?m)^(?=---\s*\ntype:)', content)

    for entry in raw_entries:
        entry = entry.strip()
        if not entry:
            continue

        # Entri muat dalam satu chunk (langsung append sebagai 1 vektor utuh)
        chunks.append(entry)

    logger.info(f"[markdown_aware_chunking] Created {len(chunks)} chunks")
    return chunks


# ============================================================
# CHUNKER 2: ESKALASI — MySSC & Incident
# ============================================================

def eskalasi_aware_chunking(content: str, include_group_prefix: bool = True) -> list[str]:
    """
    Chunking untuk Eskalasi_MySSC.txt dan Eskalasi_Incident.txt.

    Strategi:
    - Parse grup header (jika ada) sebagai konteks prefix
    - Split pada batas 'NAMA FORM:' → setiap form = 1 chunk
    - Setiap chunk berisi: [GRUP prefix] + NAMA FORM + TRIGGER KEYWORD
      + PANDUAN TIKET + Link
    - Prefix GRUP diulang di setiap chunk (prefix repetition) agar
      embedding mengetahui konteks form ini tergolong pengadaan atau insiden

    Args:
        content             : Raw string isi dokumen
        include_group_prefix: True untuk MySSC (ada GRUP), False untuk Incident
    """
    chunks = []
    content = content.replace('\r\n', '\n').strip()

    # --- 1. Parse grup header sebagai lookup table ---
    # Format: "GRUP 1: ORDER_LINK (Form Pengadaan / Permintaan)"
    current_group = None
    group_map: dict[int, str] = {}  # {posisi_char: label_grup}

    if include_group_prefix:
        for m in re.finditer(
            r'GRUP\s+(\d+)\s*:\s*(\w+)\s*\(([^)]+)\)',
            content
        ):
            group_label = f"GRUP {m.group(1)}: {m.group(2)} ({m.group(3).strip()})"
            group_map[m.start()] = group_label

    # Urutkan posisi grup agar bisa lookup "grup mana yang berlaku sebelum posisi X"
    sorted_group_positions = sorted(group_map.keys())

    def get_group_at(pos: int) -> str | None:
        """Kembalikan label grup yang berlaku pada posisi karakter `pos`."""
        active = None
        for gp in sorted_group_positions:
            if gp <= pos:
                active = group_map[gp]
            else:
                break
        return active

    # --- 2. Temukan semua blok berdasarkan delimiter '---' ---
    delimiter_pattern = re.compile(r'^---+\s*$', re.MULTILINE)
    delimiters = list(delimiter_pattern.finditer(content))
    
    blocks = []
    last_end = 0
    for delim in delimiters:
        block_content = content[last_end:delim.start()].strip()
        if block_content:
            blocks.append((last_end, block_content))
        last_end = delim.end()
    
    # Tambahkan sisa setelah delimiter terakhir
    final_block = content[last_end:].strip()
    if final_block:
        blocks.append((last_end, final_block))

    if not blocks:
        logger.warning("[eskalasi_aware_chunking] No '---' entries found")
        return chunks

    for pos, raw_block in blocks:
        # Hanya ambil blok yang memang mendefinisikan form/eskalasi
        if not raw_block or ('NAMA FORM:' not in raw_block and 'TRIGGER KEYWORD:' not in raw_block):
            continue

        # --- 3. Tambahkan prefix GRUP jika relevan ---
        group_label = get_group_at(pos) if include_group_prefix else None
        if group_label:
            chunk_text = f"[{group_label}]\n{raw_block}"
        else:
            chunk_text = raw_block

        # --- 4. Biarkan 1 form menjadi 1 vektor utuh ---
        chunks.append(chunk_text)

    logger.info(
        f"[eskalasi_aware_chunking] Created {len(chunks)} chunks "
        f"(group_prefix={'on' if include_group_prefix else 'off'})"
    )
    return chunks


# ============================================================
# ROUTER UTAMA: Pilih Chunker berdasarkan Format
# ============================================================

def route_chunking(content: str, doc_type: str | None = None) -> list[str]:
    """
    Arahkan ke chunker yang tepat berdasarkan doc_type (prioritas utama)
    atau content-based detection (fallback).

    Args:
        content  : Raw string isi dokumen
        doc_type : Nilai dari form upload — 'TROUBLESHOOT', 'ORDER_LINK',
                   atau 'INCIDENT_LINK'. Jika diberikan, digunakan sebagai
                   primary signal sehingga content-based detection hanya
                   sebagai fallback.
                   Trade-off: doc_type dari user lebih reliable karena
                   dipilih eksplisit, tapi content-based detection tetap
                   berguna jika doc_type None (e.g. ingestion via script).
    Returns:
        List of chunk strings siap untuk di-embed.
    """
    DOC_TYPE_MAP = {
        'TROUBLESHOOT':   'kb_markdown',
        'ORDER_LINK':     'eskalasi_myssc',
        'INCIDENT_LINK':  'eskalasi_incident',
    }

    if doc_type and doc_type.upper() in DOC_TYPE_MAP:
        fmt = DOC_TYPE_MAP[doc_type.upper()]
        logger.info(f"[route_chunking] Format from doc_type='{doc_type}': '{fmt}'")
    else:
        fmt = detect_document_format(content)
        logger.info(f"[route_chunking] Format from content detection: '{fmt}'")

    if fmt == 'kb_markdown':
        return markdown_aware_chunking(content)

    elif fmt == 'eskalasi_myssc':
        return eskalasi_aware_chunking(content, include_group_prefix=True)

    elif fmt == 'eskalasi_incident':
        return eskalasi_aware_chunking(content, include_group_prefix=False)

    else:
        # Fallback: coba markdown chunking; jika gagal hasilkan 1 chunk besar
        logger.warning(
            "[route_chunking] Unknown format, falling back to markdown_aware_chunking"
        )
        chunks = markdown_aware_chunking(content)
        if not chunks:
            logger.warning("[route_chunking] Fallback produced 0 chunks; using raw content")
            chunks = [content]
        return chunks


# ============================================================
# INGEST DOCUMENT
# ============================================================

def ingest_document(document, vector_store=None, embedding_service=None):
    """
    Proses dokumen: delete chunk lama → detect format → chunking
    → embedding → simpan ke DB.

    Args:
        document         : Instance model Document (harus punya .id, .content, .chunks)
        vector_store     : Opsional, tidak digunakan saat ini (reserved)
        embedding_service: Opsional; jika None akan dibuat EmbeddingService baru
                           (gunakan parameter ini untuk unit testing / dependency injection)

    Returns:
        True  jika ingestion berhasil (minimal 1 chunk tersimpan)
        False jika dokumen tidak punya konten
    """
    # --- Hapus chunk lama ---
    deleted_count = document.chunks.all().count()
    document.chunks.all().delete()
    logger.info(
        "Deleted old chunks",
        extra={"document_id": document.id, "deleted_count": deleted_count}
    )

    if not document.content:
        logger.warning(
            "Document has no content, skipping ingestion",
            extra={"document_id": document.id}
        )
        return False

    embedding_service = embedding_service or get_embedding_service()

    # --- Chunking: gunakan doc_type dari model jika tersedia ---
    doc_type = getattr(document, 'doc_type', None)
    chunks = route_chunking(document.content, doc_type=doc_type)

    if not chunks:
        logger.error(
            "Chunking produced 0 chunks",
            extra={"document_id": document.id}
        )
        return False

    # --- Extract metadata untuk monitoring & logging ---
    chunk_metadata = []
    for chunk in chunks:
        metadata = extract_metadata_from_chunk(chunk)
        chunk_metadata.append(metadata)

    logger.info(
        "Chunking complete",
        extra={
            "document_id": document.id,
            "doc_type": doc_type,
            "content_format": detect_document_format(document.content),
            "total_chunks": len(chunks),
            "avg_chunk_len": round(sum(len(c) for c in chunks) / len(chunks)),
            "categories": list(set(
                m.get("primary_category")
                for m in chunk_metadata
                if m.get("primary_category")
            )),
            "structure_types": list(set(
                m.get("structure_type")
                for m in chunk_metadata
                if m.get("structure_type")
            )),
        }
    )

    # --- Embed & simpan setiap chunk ---
    created = 0
    for index, chunk_text in enumerate(chunks):
        try:
            vector = embedding_service.embed_text(chunk_text)

            if vector is None:
                logger.warning(
                    "Embedding returned None, skipping chunk",
                    extra={"document_id": document.id, "chunk_index": index}
                )
                continue

            DocumentChunk.objects.create(
                document=document,
                chunk_index=index,
                content=chunk_text,
                embedding_vector=embedding_service.to_bytes(vector)
            )
            created += 1

        except Exception as e:
            logger.error(
                "Failed to embed/save chunk",
                extra={
                    "document_id": document.id,
                    "chunk_index": index,
                    "error": str(e),
                }
            )

    logger.info(
        "Ingestion complete",
        extra={
            "document_id": document.id,
            "chunks_created": created,
            "chunks_total": len(chunks),
            "success_rate": f"{round(created / len(chunks) * 100)}%",
        }
    )

    # ── HOT-RELOAD: Sync in-memory indices after DB write ─────────────────────
    # Problem: FAISS VectorStore and BM25 index are loaded once at startup.
    # New chunks saved to the DB are invisible to the running search engine
    # until the server is restarted — causing the stale-index bug where
    # freshly uploaded documents score 0.0 on every query.
    #
    # Fix: after all chunks are committed, immediately:
    #   1. Reload the singleton FAISS index from DB (all rows, including new ones)
    #   2. Invalidate the BM25 cache so it rebuilds lazily on next search call
    #
    # This is safe to do synchronously because:
    #   - ingest_document() is already called in a request context (not streaming)
    #   - FAISS load is fast (<1 s for typical knowledge bases)
    #   - Failure here does NOT undo the DB write — ingestion already succeeded.
    if created > 0:
        try:
            from apps.rag.apps import get_vector_store
            from apps.rag.services.retrieval import invalidate_bm25_index

            vs = get_vector_store()
            if vs is not None:
                vs.load_embeddings()
                logger.info(
                    "vector_store_reloaded",
                    extra={
                        "document_id": document.id,
                        "chunks_added": created,
                        "reason": "post_ingestion_sync",
                    }
                )
            else:
                logger.warning(
                    "vector_store_reload_skipped",
                    extra={"reason": "singleton is None (startup failure?)"}
                )

            invalidate_bm25_index()

        except Exception as reload_err:
            # Non-fatal: DB write succeeded; search engine will be stale until
            # next server restart or manual reload, but data is not lost.
            logger.error(
                "vector_store_reload_failed",
                extra={"document_id": document.id, "error": str(reload_err)}
            )
    # ─────────────────────────────────────────────────────────────────────────

    return created > 0