from django.apps import AppConfig


class RagConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rag'
    verbose_name = 'RAG'

    # Singleton holder — satu instance untuk seluruh proses Django
    _vector_store = None
    _embedding_service = None

    def ready(self):
        """
        Dipanggil Django tepat sekali saat aplikasi siap.
        Guard mencegah double-load pada Django dev server auto-reloader.
        """
        if RagConfig._vector_store is None:
            try:
                # Import dari embedding.py (bukan embedding_service.py)
                # embedding.py adalah versi lengkap dengan device="cpu"
                from apps.rag.services.embedding import EmbeddingService
                from apps.rag.services.vector_store import VectorStore

                import logging
                logger = logging.getLogger("chatbot")

                logger.info("rag_init_start", extra={"msg": "Loading EmbeddingService..."})
                RagConfig._embedding_service = EmbeddingService()

                logger.info("rag_init_vector", extra={"msg": "Loading VectorStore..."})
                # VectorStore sekarang menerima embedding_service sebagai parameter
                # Tidak perlu load model dua kali — gunakan singleton yang sama
                RagConfig._vector_store = VectorStore(
                    embedding_service=RagConfig._embedding_service
                )

                logger.info("rag_init_ok", extra={"msg": "RAG singleton ready."})

            except Exception as e:
                import logging
                logging.getLogger("chatbot").warning(
                    "rag_init_skipped", extra={"reason": str(e)}
                )


def get_vector_store():
    return RagConfig._vector_store


def get_embedding_service():
    if RagConfig._embedding_service is None:
        # Lazy fallback: jika ready() gagal saat startup, buat instance baru
        import logging
        logging.getLogger("chatbot").warning(
            "get_embedding_service_fallback",
            extra={"reason": "Singleton is None, creating fresh instance"}
        )
        from apps.rag.services.embedding import EmbeddingService
        RagConfig._embedding_service = EmbeddingService()
    return RagConfig._embedding_service