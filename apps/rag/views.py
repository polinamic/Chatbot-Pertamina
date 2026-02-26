from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.permissions import AllowAny

from django.db import transaction
from datetime import datetime
import uuid
import pyodbc

from apps.rag.services import vector_store

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

    permission_classes = [AllowAny]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(is_active=True)

    def get_permissions(self):
        return [AllowAny()]

    # ======================================================
    # PROCESS DOCUMENT (CHUNK + EMBEDDING)
    # ======================================================

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def process(self, request, pk=None):

        document = self.get_object()

        # Hapus chunk lama
        document.chunks.all().delete()

        content = document.content

        if not content:
            return Response(
                {"error": "Document content kosong"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Split sederhana 500 karakter
        chunks = [content[i:i+500] for i in range(0, len(content), 500)]

        embedding_service = EmbeddingService()

        for index, chunk_text in enumerate(chunks):
            vector = embedding_service.embed_text(chunk_text)

            DocumentChunk.objects.create(
                document=document,
                chunk_index=index,
                content=chunk_text,
                embedding_vector=embedding_service.to_bytes(vector)
            )

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
        vector_store = VectorStore()
        vector_store.load_embeddings()

        embedding_service = EmbeddingService()

        vector_store.load_embeddings()
        print("Loaded:", len(vector_store.ids))

        # Jalankan RAG
        answer = chat(query, vector_store, embedding_service)

        return Response({
            "query": query,
            "answer": answer
        }, status=status.HTTP_200_OK)

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import Document, DocumentChunk
from .services.embedding import EmbeddingService


@csrf_exempt
def upload_knowledge(request):

    if request.method == "POST":

        title = request.POST.get("title")
        file = request.FILES.get("file")

        if not file:
            return render(request, "rag/upload.html", {"message": "File tidak ditemukan"})

        content = file.read().decode("utf-8")

        # 1️⃣ Simpan Document
        document = Document.objects.create(
            title=title,
            content=content,
            is_active=True
        )

        # 2️⃣ Split & Embedding
        embedding_service = EmbeddingService()
        chunks = [content[i:i+500] for i in range(0, len(content), 500)]

        for index, chunk_text in enumerate(chunks):
            vector = embedding_service.embed_text(chunk_text)

            DocumentChunk.objects.create(
                document=document,
                chunk_index=index,
                content=chunk_text,
                embedding_vector=embedding_service.to_bytes(vector)
            )

        return render(request, "rag/upload.html", {
            "message": "Upload dan embedding berhasil!"
        })

    return render(request, "rag/upload.html")