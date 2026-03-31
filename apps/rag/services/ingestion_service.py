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

# Prefix yang diulang saat 1 entri KB harus dipecah jadi beberapa chunk.
# Ini menjaga konteks kategori tetap ada di setiap sub-chunk.
CATEGORY_DELIMITER = "KATEGORI:"


def category_aware_chunking(content: str) -> list[str]:
    """
    PERBAIKAN UTAMA: Split berdasarkan delimiter 'KATEGORI:' bukan '\n\n'.

    Setiap entri KB (1 KATEGORI) dijaga utuh dalam satu chunk.
    Jika ada entri yang terlalu panjang (> MAX_CHUNK_SIZE),
    pecah lagi dengan header kategori diulang di setiap sub-chunk.

    Returns:
        List of chunks, masing-masing mengandung header KATEGORI: yang lengkap.
    """
    chunks = []

    # Split berdasarkan 'KATEGORI:' — setiap elemen adalah 1 entri KB
    raw_sections = content.split(CATEGORY_DELIMITER)

    for section in raw_sections:
        section = section.strip()
        if not section:
            continue

        # Rekonstruksi teks lengkap dengan header
        full_text = f"{CATEGORY_DELIMITER} {section}"

        if len(full_text) <= MAX_CHUNK_SIZE:
            # Entri KB muat dalam 1 chunk — simpan utuh
            chunks.append(full_text)
        else:
            # Entri KB terlalu panjang — pecah tapi pertahankan header
            # Ambil baris pertama sebagai header (KATEGORI: NAMA_KATEGORI)
            lines = full_text.split("\n")
            header = lines[0]  # Contoh: "KATEGORI: JARINGAN_WIFI_LIMITED_ACCESS"

            # Gabungkan kembali teks tanpa header untuk dipecah
            body = "\n".join(lines[1:])

            # Pecah body per MAX_CHUNK_SIZE, prefix header di setiap bagian
            for i in range(0, len(body), MAX_CHUNK_SIZE):
                sub_body = body[i:i + MAX_CHUNK_SIZE].strip()
                if sub_body:
                    # Header diulang agar setiap sub-chunk tetap punya konteks kategori
                    sub_chunk = f"{header}\n{sub_body}"
                    chunks.append(sub_chunk)

            logger.warning(
                "KB entry too long, split into sub-chunks",
                extra={
                    "category": header,
                    "original_len": len(full_text),
                    "sub_chunks": len([i for i in range(0, len(body), MAX_CHUNK_SIZE)]),
                }
            )

    return chunks


def ingest_document(document):
    """
    Proses dokumen: delete chunk lama → chunking → embedding → simpan.

    Perubahan dari versi lama:
    - Gunakan category_aware_chunking() bukan smart_chunking()
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
        return

    embedding_service = EmbeddingService()

    # PERBAIKAN: Gunakan category-aware chunking
    chunks = category_aware_chunking(document.content)
    
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