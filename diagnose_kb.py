"""
diagnose_kb.py — Script Diagnostik Knowledge Base SITI

Jalankan kapanpun untuk cek kondisi chunk di database:
    python manage.py shell < diagnose_kb.py
    # ATAU
    python diagnose_kb.py   (jika dijalankan langsung dengan Django setup)

Output: laporan lengkap kondisi chunk + rekomendasi tindakan.
"""

import os
import sys
import django

# ── 1. Wajib set environment variable DULU ────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# ── 2. Pemanasan Django DULU ────
django.setup()

# ── 3. BARU boleh import models setelah Django siap ────
from apps.rag.models import Document, DocumentChunk
import numpy as np


# ════════════════════════════════════════════════════════════
#  WARNA TERMINAL
# ════════════════════════════════════════════════════════════
RED   = "\033[91m"
YLW   = "\033[93m"
GRN   = "\033[92m"
BLU   = "\033[94m"
BOLD  = "\033[1m"
RST   = "\033[0m"

def ok(msg):    print(f"  {GRN}✓{RST} {msg}")
def warn(msg):  print(f"  {YLW}⚠{RST} {msg}")
def err(msg):   print(f"  {RED}✗{RST} {msg}")
def info(msg):  print(f"  {BLU}•{RST} {msg}")
def head(msg):  print(f"\n{BOLD}{msg}{RST}")


# ════════════════════════════════════════════════════════════
#  CEK PER DOKUMEN
# ════════════════════════════════════════════════════════════

def diagnose_document(doc):
    chunks = list(DocumentChunk.objects.filter(document=doc))

    head(f"📄 [{doc.id}] {doc.title}  (doc_type={doc.doc_type})")
    info(f"Total chunks: {len(chunks)}")

    if not chunks:
        err("TIDAK ADA CHUNK — dokumen belum diproses atau ingestion gagal!")
        return

    # ── 1. Orphan chunks ──────────────────────────────────
    orphans = [c for c in chunks if not c.content.startswith("KATEGORI:")]
    if orphans:
        err(f"ORPHAN CHUNKS: {len(orphans)} chunk tidak punya header 'KATEGORI:'")
        err("→ Ini penyebab RAG menjawab salah. Re-upload dokumen dengan")
        err("  ingestion_service.py yang sudah diperbaiki.")
        for c in orphans[:3]:
            print(f"     [{c.chunk_index}] preview: {repr(c.content[:80])}")
        if len(orphans) > 3:
            print(f"     ... dan {len(orphans)-3} lainnya")
    else:
        ok("Tidak ada orphan chunk — semua chunk punya header KATEGORI")

    # ── 2. Missing embedding ──────────────────────────────
    no_embed = [c for c in chunks if not c.embedding_vector]
    if no_embed:
        err(f"MISSING EMBEDDING: {len(no_embed)} chunk tidak punya vector")
        err("→ Hapus dan re-upload dokumen")
    else:
        ok(f"Semua {len(chunks)} chunk punya embedding vector")

    # ── 3. Distribusi panjang chunk ───────────────────────
    lengths = [len(c.content) for c in chunks]
    avg = sum(lengths) // len(lengths)
    mn, mx = min(lengths), max(lengths)
    info(f"Panjang chunk: min={mn}, max={mx}, avg={avg}")

    short = [c for c in chunks if len(c.content) < 200]
    if short:
        warn(f"{len(short)} chunk sangat pendek (<200 char) — mungkin terpotong tidak sempurna")
        for c in short[:2]:
            print(f"     [{c.chunk_index}] {repr(c.content[:100])}")

    # ── 4. Duplikat chunk ──────────────────────────────────
    contents = [c.content for c in chunks]
    dupes = len(contents) - len(set(contents))
    if dupes > 0:
        warn(f"{dupes} chunk duplikat — mungkin dokumen di-upload lebih dari sekali")
    else:
        ok("Tidak ada chunk duplikat")

    # ── 5. Cek embedding dimension konsisten ──────────────
    dims = set()
    for c in chunks:
        if c.embedding_vector:
            vec = np.frombuffer(c.embedding_vector, dtype=np.float32)
            dims.add(len(vec))
    if len(dims) > 1:
        err(f"INCONSISTENT EMBEDDING DIMENSION: {dims}")
        err("→ Dokumen mungkin di-embed dengan model berbeda. Re-upload semua.")
    elif dims:
        ok(f"Embedding dimension konsisten: {list(dims)[0]}d")

    # ── 6. Ringkasan per kategori ─────────────────────────
    head("   Daftar kategori yang ter-embed:")
    for c in chunks[:5]:
        first_line = c.content.split("\n")[0]
        print(f"     [{c.chunk_index}] {first_line[:70]}")
    if len(chunks) > 5:
        print(f"     ... dan {len(chunks)-5} chunk lainnya")


# ════════════════════════════════════════════════════════════
#  CEK RAG RETRIEVAL LIVE
# ════════════════════════════════════════════════════════════

def test_rag_query(query: str, expected_category: str = None):
    """
    Uji RAG secara langsung dengan query tertentu.
    Tampilkan top-3 hasil beserta score dan preview konten.
    """
    head(f"🔍 RAG Test Query: \"{query}\"")
    if expected_category:
        info(f"Expected category: {expected_category}")

    try:
        from apps.rag.apps import get_embedding_service, get_vector_store
        from apps.rag.services.retrieval import retrieve_context

        embedding_service = get_embedding_service()
        vector_store      = get_vector_store()

        if not embedding_service or not vector_store:
            err("embedding_service atau vector_store belum diinisialisasi")
            err("→ Pastikan Django sudah fully started (apps.py ready() dipanggil)")
            return

        results = retrieve_context(
            query, vector_store, embedding_service,
            doc_type="TROUBLESHOOT", top_k=3
        )

        if not results:
            err("RAG tidak menemukan hasil apapun!")
            err("→ Kemungkinan vector store kosong atau semua score di bawah threshold")
            return

        print(f"\n  Top {len(results)} hasil:")
        for i, r in enumerate(results):
            score   = r.get("score", 0)
            preview = r.get("content", "")[:100].replace("\n", " ")
            first_line = r.get("content", "").split("\n")[0]

            color = GRN if score >= 0.60 else (YLW if score >= 0.40 else RED)
            print(f"\n  [{i+1}] Score: {color}{score:.3f}{RST}")
            print(f"       Kategori: {first_line}")
            print(f"       Preview:  {preview}...")

            if expected_category and expected_category in first_line:
                ok(f"MATCH! Kategori yang diharapkan ditemukan di posisi {i+1}")

        # Cek apakah expected category ada di hasil
        if expected_category:
            found = any(expected_category in r.get("content","").split("\n")[0]
                        for r in results)
            if not found:
                warn(f"Kategori '{expected_category}' TIDAK ditemukan di top-3")
                warn("→ Kemungkinan: orphan chunks, atau perlu tuning MIN_SIMILARITY")

    except ImportError as e:
        err(f"Import error: {e}")
        err("→ Jalankan dari manage.py shell atau pastikan path apps.py benar")
    except Exception as e:
        err(f"Error saat RAG test: {e}")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main():
    print(f"\n{'═'*60}")
    print(f"{BOLD}  SITI Knowledge Base Diagnostics{RST}")
    print(f"{'═'*60}")

    # ── Ringkasan global ──────────────────────────────────
    head("📊 Ringkasan Global")
    docs   = Document.objects.all()
    chunks = DocumentChunk.objects.all()
    no_vec = DocumentChunk.objects.filter(embedding_vector=None)

    info(f"Total dokumen   : {docs.count()}")
    info(f"Total chunks    : {chunks.count()}")
    info(f"Missing vectors : {no_vec.count()}")

    if chunks.count() == 0:
        err("TIDAK ADA CHUNK di database!")
        err("→ Upload minimal 1 dokumen KB terlebih dahulu")
        return

    # ── Per dokumen ───────────────────────────────────────
    head("📋 Diagnosa Per Dokumen")
    for doc in docs:
        diagnose_document(doc)

    # ── RAG Live Test ──────────────────────────────────────
    head("🧪 RAG Live Test")
    print(f"  {YLW}(Test ini membutuhkan vector store ter-load di memory){RST}")
    print(f"  {YLW}Skip jika dijalankan di luar Django server context{RST}")

    test_cases = [
        (
            "laptop gak bisa konek Wi-Fi kantor, ikon tanda seru kuning",
            "JARINGAN_WIFI_LIMITED_ACCESS"
        ),
        (
            "printer tidak terdeteksi di komputer",
            "PRINTER_OFFLINE_NETWORK"
        ),
        (
            "tidak bisa login Windows, akun terkunci",
            "AKUN_AD_LOCKED"
        ),
        (
            "VPN sering disconnect sendiri",
            "VPN_DISCONNECT_INTERMITTENT"
        ),
    ]

    for query, expected in test_cases:
        test_rag_query(query, expected)
        print()

    # ── Ringkasan rekomendasi ─────────────────────────────
    head("💡 Rekomendasi")
    all_chunks  = list(DocumentChunk.objects.all())
    all_orphans = [c for c in all_chunks if not c.content.startswith("KATEGORI:")]

    if all_orphans:
        print(f"""
  {RED}ACTION REQUIRED:{RST}
  {len(all_orphans)} orphan chunk ditemukan di database.

  Langkah perbaikan:
  1. Pastikan ingestion_service.py sudah diganti dengan versi terbaru
     (category_aware_chunking, bukan smart_chunking)
  2. Di Admin Dashboard → Knowledge Base Manager:
     a. Hapus semua dokumen yang bermasalah (tombol 🗑)
     b. Upload ulang dokumen yang sama
  3. Jalankan script ini lagi untuk verifikasi: python manage.py shell < diagnose_kb.py
""")
    else:
        print(f"""
  {GRN}Semua chunk dalam kondisi baik.{RST}
  Jika RAG masih memberikan jawaban salah, coba tuning threshold:
    export MIN_SIMILARITY=0.55   (turunkan jika terlalu banyak disclaimer)
    export MIN_SIMILARITY=0.65   (naikkan jika terlalu banyak false match)
""")

    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()