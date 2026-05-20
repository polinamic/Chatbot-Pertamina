from django.contrib import admin
from django.contrib import messages
from .models import Document, DocumentChunk
import logging

logger = logging.getLogger("chatbot")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'category', 'is_active', 'created_at']
    search_fields = ['title', 'category']
    list_filter = ['category', 'is_active']
    ordering = ['-created_at']

    def save_model(self, request, obj, form, change):
        """
        Override: after saving the Document row, run the full ingestion pipeline
        (chunking → embedding → DB → FAISS hot-reload) so that documents uploaded
        via Django Admin are immediately searchable without a server restart.

        Without this override, Admin only writes the Document row to the DB.
        The in-memory FAISS index never learns about the new content, causing
        zero-score retrieval until the next server restart.
        """
        super().save_model(request, obj, form, change)

        if not obj.content:
            messages.warning(
                request,
                f'Document "{obj.title}" saved but has no content — ingestion skipped. '
                "Please populate the 'content' field and save again."
            )
            return

        try:
            from apps.rag.services.ingestion_service import ingest_document
            from apps.rag.apps import get_vector_store, get_embedding_service

            embedding_service = get_embedding_service()
            vector_store = get_vector_store()

            success = ingest_document(obj, vector_store=vector_store, embedding_service=embedding_service)

            if success:
                chunk_count = obj.chunks.count()
                messages.success(
                    request,
                    f'Document "{obj.title}" ingested successfully — '
                    f'{chunk_count} chunk(s) embedded and FAISS index reloaded.'
                )
                logger.info("admin_ingest_ok", extra={
                    "document_id": obj.id,
                    "title": obj.title,
                    "chunks": chunk_count,
                })
            else:
                messages.error(
                    request,
                    f'Document "{obj.title}" saved but ingestion produced 0 chunks. '
                    "Check the content format."
                )
        except Exception as e:
            messages.error(
                request,
                f'Document "{obj.title}" saved but ingestion failed: {e}. '
                "The FAISS index may be stale — restart the server if needed."
            )
            logger.error("admin_ingest_failed", extra={
                "document_id": obj.id,
                "error": str(e),
            })


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'chunk_index', 'created_at']
    search_fields = ['document__title']
    ordering = ['document', 'chunk_index']