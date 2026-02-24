from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from django.db import transaction
from datetime import datetime
import uuid
import pyodbc

from .models import Document, DocumentChunk
from .serializers import DocumentSerializer, DocumentListSerializer

from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.chat_service import chat


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=chatbot_pertamina;"
        "Trusted_Connection=yes;"
    )


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk mengelola documents untuk RAG
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'process']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    # ======================================================
    # PROCESS DOCUMENT (CHUNK + EMBEDDING)
    # ======================================================

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser()])
    def process(self, request, pk=None):

        document = self.get_object()

        # Hapus chunk lama jika ada
        DocumentChunk.objects.filter(document=document).delete()

        content = document.content

        if not content:
            return Response(
                {"error": "Document content kosong"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Split sederhana 500 karakter
        chunks = [content[i:i+500] for i in range(0, len(content), 500)]

        embedding_service = EmbeddingService()

        connection = get_connection()
        cursor = connection.cursor()

        for chunk_text in chunks:
            chunk_id = str(uuid.uuid4())

            # Generate embedding
            vector = embedding_service.embed_text(chunk_text)
            vector_bytes = embedding_service.to_bytes(vector)

            # Simpan ke SQL Server langsung
            cursor.execute("""
                INSERT INTO DocumentChunk
                (document_chunk_id, document_id, chunk_text, embedding_vector, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                chunk_id,
                document.document_id,
                chunk_text,
                vector_bytes,
                datetime.now()
            )

        connection.commit()

        return Response(
            {"message": "Document processed successfully"},
            status=status.HTTP_200_OK
        )

    # ======================================================
    # SEARCH (RAG ENDPOINT)
    # ======================================================

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated()])
    def search(self, request):

        query = request.data.get("query")

        if not query:
            return Response(
                {"error": "Query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Setup RAG
        connection = get_connection()
        vector_store = VectorStore(connection)
        vector_store.load_embeddings()

        embedding_service = EmbeddingService()

        # Jalankan RAG
        answer = chat(query, vector_store, embedding_service)

        return Response({
            "query": query,
            "answer": answer
        }, status=status.HTTP_200_OK)