"""
ingestion_service.py — Perbaikan Chunking Strategy

DIAGNOSIS ROOT CAUSE:
=====================
Metode lama (smart_chunking) menggunakan split('\n\n') lalu potong per 800 char.
Ini menghasilkan DUA masalah fatal:

  [MASALAH 1] ORPHAN CHUNKS — 81 dari 162 chunk tidak punya header 'KATEGORI:'.
  Penyebab: Setiap entri KB panjangnya 1000-1300 char > 800, sehingga dipotong
  di tengah kalimat. Chunk kedua kehilangan konteks kategorinya.

  Contoh chunk rusak:
    'or, tekan Ctrl+Alt+Del, pilih "Lock", lalu buka kunci dengan password...'
  → Tidak ada info ini tentang apa. Embedding-nya tidak akurat.

  [MASALAH 2] FALSE MATCH — Kata 'Wi-Fi' muncul di 15 chunk berbeda dari
  berbagai kategori (AKUN_AD_LOCKED, AKUN_AD_LOOP_LOGIN, dll karena langkah
  troubleshoot sering menyebut 'Wi-Fi' atau 'LAN'). RAG bisa mengembalikan
  chunk dari kategori yang SALAH dengan similarity score yang cukup tinggi.

  [AKIBAT DI CHAT]: User tanya tentang Wi-Fi tanda seru kuning →
  SEHARUSNYA match JARINGAN_WIFI_LIMITED_ACCESS → TAPI bisa match
  chunk AKUN_AD_LOOP_LOGIN (yang juga bicara tentang Wi-Fi di langkah 1-3)
  → LLM mendapat konteks SOP yang salah → jawaban generik dari pengetahuan
  sendiri atau campuran SOP yang tidak relevan.

SOLUSI: Category-Aware Chunking
================================
Split berdasarkan delimiter 'KATEGORI:' sehingga setiap chunk = 1 entri KB
lengkap dengan header + konteks masalah + langkah perbaikan.

Jika 1 entri KB > MAX_CHUNK_SIZE, pecah dengan mempertahankan header di
setiap sub-chunk (prefix repetition) agar embedding tetap akurat.
"""

import logging
from apps.rag.models import DocumentChunk
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.metadata_manager import extract_metadata_from_chunk

logger = logging.getLogger(__name__)

# ============================================================
# KONFIGURASI CHUNKING
# ============================================================

# Maksimal karakter per chunk sebelum dipecah lagi.
# Dengan format KB saat ini (~1000-1300 char per entri),
# nilai 1500 memastikan hampir semua entri muat dalam 1 chunk.
# Turunkan ke 800 jika model embedding punya context limit ketat.
MAX_CHUNK_SIZE = 1500

def markdown_aware_chunking(content: str) -> list[str]:
    """
    Chunking untuk format Markdown dengan YAML frontmatter.

    Split berdasarkan positive lookahead YAML frontmatter boundary.
    Gunakan regex: re.split(r'(?m)^(?=---\s*\ntype:)', content)
    untuk memisahkan entry yang dimulai dengan ---\n type:.
    """
    import re

    chunks = []
    content = content.replace('\r\n', '\n').strip()
    raw_entries = re.split(r'(?m)^(?=---\s*$)', content)

    for entry in raw_entries:
        entry = entry.strip()
        if not entry:
            continue

        if len(entry) <= MAX_CHUNK_SIZE:
            chunks.append(entry)
            continue

        lines = entry.split('\n')
        frontmatter_end = 0
        for i, line in enumerate(lines):
            if line.strip() == '' and i > 0:
                frontmatter_end = i
                break

        frontmatter = '\n'.join(lines[:frontmatter_end])
        body = '\n'.join(lines[frontmatter_end:]) if frontmatter_end < len(lines) else ''

        if not frontmatter:
            frontmatter = entry
            body = ''

        for i in range(0, len(body), MAX_CHUNK_SIZE):
            sub_body = body[i:i + MAX_CHUNK_SIZE].strip()
            if sub_body:
                chunks.append(f"{frontmatter}\n\n{sub_body}")

        logger.warning(
            "KB entry too long, split into sub-chunks",
            extra={
                'original_len': len(entry),
                'sub_chunks': len([i for i in range(0, len(body), MAX_CHUNK_SIZE)]),
            }
        )

    logger.info(f"Markdown aware chunking created {len(chunks)} chunks")
    return chunks


def ingest_document(document, vector_store=None, embedding_service=None):
    """
    Proses dokumen: delete chunk lama → chunking → embedding → simpan.

    Perubahan dari versi lama:
    - Gunakan markdown_aware_chunking() bukan smart_chunking()
    - Singleton-friendly: terima embedding_service dari luar (opsional)
    """

    # Hapus chunk lama
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

    embedding_service = embedding_service or EmbeddingService()

    # Semua dokumen sekarang diproses melalui Markdown-aware chunking
    chunks = markdown_aware_chunking(document.content)
    
    # Extract metadata dari chunks untuk monitoring
    chunk_metadata = []
    for chunk in chunks:
        metadata = extract_metadata_from_chunk(chunk)
        chunk_metadata.append(metadata)

    logger.info(
        "Chunking complete",
        extra={
            "document_id": document.id,
            "total_chunks": len(chunks),
            "avg_chunk_len": round(sum(len(c) for c in chunks) / len(chunks)) if chunks else 0,
            "categories": list(set([m.get("primary_category") for m in chunk_metadata if m.get("primary_category")])),
            "structure_types": list(set([m.get("structure_type") for m in chunk_metadata if m.get("structure_type")])),
        }
    )

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
                "Failed to embed chunk",
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
        }
    )

    return True