from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect

from datetime import datetime
import uuid
import pyodbc

# Optional imports
try:
    from apps.rag.services import vector_store
    HAS_VECTOR_STORE = True
except ImportError:
    HAS_VECTOR_STORE = False

from .models import Document
from .serializers import DocumentSerializer

from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.chat_service import chat
from apps.rag.services.ingestion_service import ingest_document


class DocumentViewSet(viewsets.ModelViewSet):

    permission_classes = [AllowAny]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(is_active=True)

    # ======================================================
    # PROCESS DOCUMENT (RE-EMBED EXISTING DOCUMENT)
    # ======================================================

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def process(self, request, pk=None):

        document = self.get_object()

        if not document.content:
            return Response(
                {"error": "Document content kosong"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ingest_document(document)
        except Exception as e:
            return Response(
                {"error": f"Embedding gagal: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"message": "Document processed successfully"},
            status=status.HTTP_200_OK
        )

    # ======================================================
    # SEARCH (RAG ENDPOINT)
    # ======================================================

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def search(self, request):

        query = request.data.get("query")

        if not query:
            return Response(
                {"error": "Query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Load vector store
            vector_store = VectorStore()
            vector_store.load_embeddings()

            # Initialize embedding service
            embedding_service = EmbeddingService()

            # Run RAG chat pipeline
            answer = chat(query, vector_store, embedding_service)

        except Exception as e:
            return Response(
                {"error": f"RAG processing error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "query": query,
            "answer": answer
        }, status=status.HTTP_200_OK)


# ======================================================
# UPLOAD KNOWLEDGE PAGE
# ======================================================

@csrf_exempt
def upload_knowledge(request):

    if request.method == "POST":

        title = request.POST.get("title")
        file = request.FILES.get("file")

        if not file:
            return render(
                request,
                "rag/upload.html",
                {"message": "File tidak ditemukan"}
            )

        try:
            content = file.read().decode("utf-8")

            document = Document.objects.create(
                title=title,
                content=content,
                is_active=True
            )

            ingest_document(document)

        except Exception as e:
            return render(
                request,
                "rag/upload.html",
                {"message": f"Upload gagal: {str(e)}"}
            )

        return render(
            request,
            "rag/upload.html",
            {"message": "Upload dan embedding berhasil!"}
        )

    return render(request, "rag/upload.html")

    """
    Redirect to dashboard knowledge base
    """

    if request.method == "GET":
        return redirect('dashboard:knowledge_base')

    return redirect('dashboard:knowledge_base')