from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from django.shortcuts import render, redirect
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages as django_messages

import json
import time
import logging
import ollama

from .models import Document, DocumentChunk  # apps.rag.models — hanya model RAG
from .serializers import DocumentSerializer   # serializer untuk Document RAG

logger = logging.getLogger("chatbot")

# ==============================
# LAZY IMPORT CHAT ENGINE
#
# Import chat() dari apps.rag.services.chat_service
# dilakukan secara lazy agar tidak crash saat Django
# menjalankan manage.py migrate atau collectstatic.
# ==============================

def _get_chat_fn():
    from apps.rag.services.chat_service import chat as chat_fn
    return chat_fn

def _get_rag_dependencies():
    """
    Ambil vector_store dan embedding_service dari singleton AppConfig.
    Cara setup singleton ada di docstring chat_service.py (bagian apps/rag/apps.py).
    """
    from apps.rag.apps import get_vector_store, get_embedding_service
    return get_vector_store(), get_embedding_service()


# ==============================
# DOCUMENT VIEWSET
#
# ViewSet untuk CRUD dokumen knowledge base (RAG).
# Dipakai oleh router di urls.py:
#   router.register(r'documents', DocumentViewSet, basename='document')
# ==============================

class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk mengelola Document knowledge base.
    Endpoint otomatis dari router:
      GET    /api/v1/rag/documents/          → list
      POST   /api/v1/rag/documents/          → create
      GET    /api/v1/rag/documents/{id}/     → retrieve
      PUT    /api/v1/rag/documents/{id}/     → update
      DELETE /api/v1/rag/documents/{id}/     → destroy
      POST   /api/v1/rag/documents/search/   → search (custom action)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    queryset = Document.objects.filter(is_active=True).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def search(self, request):
        """
        Cari dokumen berdasarkan query teks.
        Body: { "query": "...", "doc_type": "TROUBLESHOOT" (opsional) }
        """
        query = request.data.get('query', '').strip()
        doc_type = request.data.get('doc_type', None)

        if not query:
            return Response({'error': 'Field query wajib diisi.'}, status=400)

        try:
            vector_store, embedding_service = _get_rag_dependencies()
            from apps.rag.services.retrieval import retrieve_context
            results = retrieve_context(
                query, vector_store, embedding_service,
                doc_type=doc_type, top_k=5
            )
            return Response({'results': results})
        except Exception as e:
            logger.error("document_search_error", extra={"error": str(e)})
            return Response({'error': 'Pencarian gagal.'}, status=500)


# ==============================
# UPLOAD KNOWLEDGE BASE
#
# View untuk memproses upload dokumen dari form dashboard.
# Dipanggil via POST dari halaman dashboard knowledge base.
# ==============================

@csrf_exempt
def upload_knowledge(request):
    """
    Terima upload file dokumen untuk knowledge base RAG.
    Menyimpan ke model Document, kemudian memproses chunking & embedding.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    uploaded_file = request.FILES.get('file')
    title = request.POST.get('title', '').strip()
    doc_type = request.POST.get('doc_type', 'TROUBLESHOOT')

    if not uploaded_file:
        return JsonResponse({'error': 'File wajib diupload.'}, status=400)

    if not title:
        title = uploaded_file.name

    try:
        doc = Document.objects.create(
            title=title,
            file=uploaded_file,
            file_name=uploaded_file.name,
            file_size=uploaded_file.size,
            doc_type=doc_type,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        # Proses chunking & embedding secara async jika tersedia,
        # atau langsung jika tidak ada task queue.
        try:
            from apps.rag.services.processor import process_document
            process_document(doc.id)
        except ImportError:
            logger.warning("upload_knowledge_no_processor",
                           extra={"doc_id": doc.id, "msg": "processor service tidak ditemukan"})

        return JsonResponse({
            'success': True,
            'doc_id': doc.id,
            'message': f'Dokumen "{title}" berhasil diupload dan sedang diproses.'
        })

    except Exception as e:
        logger.error("upload_knowledge_error", extra={"error": str(e)})
        return JsonResponse({'error': f'Upload gagal: {str(e)}'}, status=500)

# ==============================
# NEGATIVE RESPONSE DETECTION
# ==============================

NEGATIVE_WORDS = [
    "belum",
    "masih",
    "tidak",
    "nggak",
    "gak",
    "error",
    "gagal",
    "tidak bisa",
]


def is_negative_response(text: str):

    text = text.lower()

    for word in NEGATIVE_WORDS:
        if word in text:
            return True

    return False


# ==============================
# UI CATEGORY CLASSIFIER
# ==============================

def classify_ui_category(problem_history):

    categories = UINavigatorMap.objects.all()

    category_prompt = ""

    for cat in categories:
        category_prompt += f"{cat.category_name}: {cat.description}\n"

    prompt = f"""
User mengalami masalah IT berikut:

{problem_history}

Kategori yang tersedia:

{category_prompt}

Tugas Anda:
Pilih kategori yang paling cocok.

Jawab HANYA satu kata kategori.
"""

    response = ollama.chat(
        model="llama3:8b",
        messages=[
            {"role": "system", "content": "Anda adalah classifier masalah IT."},
            {"role": "user", "content": prompt}
        ],
        options={"temperature": 0}
    )

    return response["message"]["content"].strip()


# ==============================
# CHAT TEMPLATE VIEW
# ==============================

def chat_view(request):
    return render(request, 'chatbot/chat.html', {
        "conversations": [],
        "messages": []
    })


def chat_page(request):
    """Render main chat page"""
    return render(request, 'chatbot/chat.html')


# ==============================
# STREAMING CHAT ENDPOINT
# ==============================

@csrf_exempt
def stream_chat(request):
    """
    Streaming endpoint untuk token streaming LLM
    """

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    query = body.get("query")

    if not query:
        return JsonResponse({"error": "Query is required"}, status=400)

    def generate():

        try:

            stream = ollama.chat(
                model="llama3:8b",
                messages=[
                    {"role": "user", "content": query}
                ],
                stream=True
            )

            for chunk in stream:

                if "message" in chunk and "content" in chunk["message"]:
                    token = chunk["message"]["content"]
                    yield token

        except Exception as e:
            yield f"\n\n[ERROR] {str(e)}"

    return StreamingHttpResponse(
        generate(),
        content_type="text/plain"
    )


# ==============================
# SITI CHAT ENDPOINT  ← BARU
#
# Ini adalah endpoint yang menghubungkan frontend
# (chat.html) dengan chat engine (chat_v2.py).
#
# Route yang harus didaftarkan di urls.py:
#   path("api/v1/rag/chat/", views.siti_chat, name="siti_chat"),
#
# Frontend mengirim:
#   POST /api/v1/rag/chat/
#   { "query": "...", "session_id": "session_xxx" }
#
# Backend mengembalikan:
#   { "answer": "...", "session_id": "session_xxx" }
# ==============================

@csrf_exempt
def siti_chat(request):
    """
    Endpoint utama chatbot SITI.
    Menerima query dari frontend, meneruskan ke chat_v2.chat(),
    mengembalikan jawaban sebagai JSON { "answer": "..." }.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Gunakan POST."}, status=405)

    # --- Parse request body ---
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body bukan JSON valid."}, status=400)

    query = body.get("query", "").strip()
    session_id = body.get("session_id", "default")

    if not query:
        return JsonResponse({"error": "Field 'query' wajib diisi."}, status=400)

    # --- Panggil chat engine ---
    start_time = time.time()
    try:
        vector_store, embedding_service = _get_rag_dependencies()
        chat_fn = _get_chat_fn()
        answer = chat_fn(
            question=query,
            vector_store=vector_store,
            embedding_service=embedding_service,
            session_id=session_id,
        )

        # =====================================================
        # PERBAIKAN: Consume generator jika chat() mengembalikan
        # generator instead of string.
        #
        # Penyebab: _process_chat() dengan stream=False pada
        # kondisi tertentu (yield di dalam fungsi yang sama)
        # membuat Python memperlakukan seluruh fungsi sebagai
        # generator — sehingga return value-pun jadi generator.
        #
        # Solusi: Cek tipe, jika generator → join semua token.
        # =====================================================
        import types
        if isinstance(answer, (types.GeneratorType,)):
            answer = "".join(answer)

        # Pastikan answer adalah string sebelum dipakai
        if not isinstance(answer, str):
            logger.error("siti_chat_answer_not_string", extra={
                "type": type(answer).__name__,
                "session_id": session_id,
            })
            answer = str(answer)

    except Exception as e:
        logger.error("siti_chat_error", extra={"error": str(e), "session_id": session_id})
        return JsonResponse(
            {"answer": "Maaf, terjadi kesalahan pada server AI. Silakan coba lagi."},
            status=200
        )

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("siti_chat_ok", extra={
        "session_id": session_id,
        "question_length": len(query),
        "answer_length": len(answer),
        "elapsed_ms": elapsed_ms,
    })

    return JsonResponse({"answer": answer, "session_id": session_id})


# ==============================
# GET CHAT HISTORY (USER'S CONVERSATIONS)
# ==============================
def get_chat_history(request):
    """
    Get user's chat history (conversations).
    Returns list of recent conversations for the logged-in user.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed. Gunakan GET."}, status=405)
    
    # Check if user is authenticated
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({"error": "user_id parameter required"}, status=400)
    
    try:
        from django.contrib.auth.models import User
        from apps.chatbot.models import Conversation
        
        user = User.objects.get(id=user_id)
        conversations = Conversation.objects.filter(user=user).order_by('-created_at')[:10]
        
        history = []
        for conv in conversations:
            history.append({
                'id': conv.id,
                'title': conv.title,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except Exception as e:
        logger.error("get_chat_history_error", extra={"error": str(e), "user_id": user_id})
        return JsonResponse(
            {"error": "Gagal mengambil riwayat chat."},
            status=500
        )