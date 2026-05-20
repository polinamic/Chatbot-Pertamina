from django.core.management.base import BaseCommand
from apps.rag.models import DocumentChunk
from apps.rag.apps import get_embedding_service
from apps.rag.services.embedding import EmbeddingService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Re-embeds all existing DocumentChunks using the unified embedding service'

    def handle(self, *args, **options):
        self.stdout.write("Memulai proses re-embedding untuk semua DocumentChunk...")
        
        # Ambil instance embedding service dari app registry (singleton)
        embedding_service = get_embedding_service()
        if not embedding_service:
            self.stdout.write("Memuat ulang EmbeddingService (Singleton belum siap)...")
            embedding_service = EmbeddingService()

        chunks = DocumentChunk.objects.all()
        total = chunks.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING("Tidak ada DocumentChunk yang ditemukan di database."))
            return

        self.stdout.write(f"Ditemukan {total} chunks. Proses embedding sedang berjalan, harap tunggu...")

        updated_count = 0
        failed_count = 0

        for idx, chunk in enumerate(chunks, 1):
            try:
                if not chunk.content:
                    continue
                    
                vector = embedding_service.embed_text(chunk.content)
                if vector is not None:
                    chunk.embedding_vector = embedding_service.to_bytes(vector)
                    chunk.save(update_fields=['embedding_vector'])
                    updated_count += 1
                else:
                    failed_count += 1
                
                # Feedback progres per 10 dokumen
                if idx % 10 == 0 or idx == total:
                    self.stdout.write(f"Progres: {idx}/{total} (Updated: {updated_count}, Failed: {failed_count})")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Gagal memproses chunk ID {chunk.id}: {str(e)}")

        self.stdout.write(self.style.SUCCESS(
            f"\nSelesai! Berhasil mengupdate {updated_count} chunks. Gagal: {failed_count} chunks."
        ))

        # Hot-reload FAISS & BM25 so new vectors are immediately searchable
        # without needing a server restart.
        if updated_count > 0:
            try:
                from apps.rag.apps import get_vector_store
                from apps.rag.services.retrieval import invalidate_bm25_index

                vs = get_vector_store()
                if vs is not None:
                    vs.load_embeddings()
                    self.stdout.write(self.style.SUCCESS(
                        "FAISS VectorStore berhasil di-reload — vektor terbaru siap digunakan."
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        "FAISS VectorStore singleton belum diinisialisasi. "
                        "Silakan restart server secara manual."
                    ))

                invalidate_bm25_index()
                self.stdout.write("BM25 index di-invalidate — akan dibangun ulang pada query berikutnya.")

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Gagal reload index: {e}. Silakan restart server secara manual."
                ))

