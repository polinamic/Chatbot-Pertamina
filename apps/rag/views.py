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
import os
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

def _get_chat_stream_fn():
    from apps.rag.services.chat_service import chat_stream as chat_stream_fn
    return chat_stream_fn

def _get_rag_dependencies():
    """
    Ambil vector_store dan embedding_service dari singleton AppConfig.
    Cara setup singleton ada di docstring chat_service.py (bagian apps/rag/apps.py).
    """
    from apps.rag.apps import get_vector_store, get_embedding_service
    return get_vector_store(), get_embedding_service()


# ==============================
# DOCUMENT VIEWSET
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
    # Gunakan filter is_active sesuai snippet 2, urutkan berdasarkan created_at
    queryset = Document.objects.filter(is_active=True).order_by('-created_at')
    parser_classes = (MultiPartParser, FormParser)

    def create(self, request, *args, **kwargs):
        """
        Custom upload handler (DRF Route):
        1. Simpan file ke storage
        2. Chunking teks
        3. Embedding ke Vector DB (FAISS)
        """
        file_obj = request.FILES.get('file')
        doc_type = request.data.get('doc_type', 'TROUBLESHOOT')

        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Simpan metadata dokumen ke DB
        doc = Document.objects.create(
            title=file_obj.name,
            file=file_obj,
            doc_type=doc_type,
            # Menambahkan isian dari snippet 2 (opsional, disesuaikan ke model Anda)
            file_name=file_obj.name,
            file_size=file_obj.size,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        # 2. Jalankan Ingestion (Chunking & Embedding)
        from apps.rag.services.ingestion_service import ingest_document
        vector_store, embedding_service = _get_rag_dependencies()
        
        # Proses sinkronus (untuk production gunakan Celery task)
        success = ingest_document(doc, vector_store, embedding_service)

        if success:
            return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)
        else:
            # Cleanup jika gagal ingestion
            doc.delete()
            return Response({"error": "Ingestion failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
# UPLOAD KNOWLEDGE BASE (STANDALONE VIEW)
# ==============================

@csrf_exempt
def upload_knowledge(request):
    """
    Terima upload file dokumen untuk knowledge base RAG (Non-DRF route).
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
# NEGATIVE RESPONSE DETECTION & HELPERS
# ==============================

NEGATIVE_WORDS = [
    "belum", "masih", "tidak", "nggak", "gak", "error", "gagal", "tidak bisa",
]

def is_negative_response(text: str):
    text = text.lower()
    for word in NEGATIVE_WORDS:
        if word in text:
            return True
    return False

def classify_ui_category(problem_history):
    try:
        from apps.rag.models import UINavigatorMap
        categories = UINavigatorMap.objects.all()
    except ImportError:
        categories = []

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
        model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
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
                model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
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
# SITI CHAT MAIN ENDPOINT (WITH DB HISTORY)
# ==============================

@csrf_exempt
def siti_chat(request):
    """
    Endpoint utama chatbot SITI.
    Menerima query dari frontend, meneruskan ke engine,
    mengembalikan jawaban sebagai JSON { "answer": "..." }.
    Menyimpan chat history ke database.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Gunakan POST."}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body bukan JSON valid."}, status=400)

    query = body.get("query", "").strip()
    session_id = body.get("session_id", "default")
    user_id = body.get("user_id")
    # new_session=True signals the start of a fresh conversation.
    # The chat engine resets failed_steps, attempts, and all counters to 0.
    # Frontend MUST send this flag when the user opens a new chat window.
    new_session = bool(body.get("new_session", False))

    if not query:
        return JsonResponse({"error": "Field 'query' wajib diisi."}, status=400)

    # --- Get or create conversation for user ---
    conversation = None
    if user_id:
        try:
            from django.contrib.auth.models import User
            from apps.chatbot.models import Conversation
            
            user = User.objects.get(id=user_id)
            conversation = Conversation.objects.filter(user=user).order_by('-created_at').first()
            if not conversation:
                conversation = Conversation.objects.create(
                    user=user,
                    title=query[:50] + "..." if len(query) > 50 else query
                )
        except User.DoesNotExist:
            logger.warning("siti_chat_user_not_found", extra={"user_id": user_id})
        except Exception as e:
            logger.error("siti_chat_conversation_error", extra={"error": str(e)})

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
            new_session=new_session,
        )

        import types
        if isinstance(answer, (types.GeneratorType,)):
            answer = "".join(answer)

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

    # --- Simpan pesan ke database jika user terautentikasi ---
    if conversation:
        try:
            from apps.chatbot.models import Message
            Message.objects.create(
                conversation=conversation,
                role='user',
                content=query
            )
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=answer
            )
            # Update title jika masih default
            if conversation.title == query[:50] + ("..." if len(query) > 50 else ""):
                conversation.title = query[:100] + ("..." if len(query) > 100 else "")
                conversation.save()
        except Exception as e:
            logger.error("siti_chat_save_message_error", extra={"error": str(e), "user_id": user_id})

    return JsonResponse({"answer": answer, "session_id": session_id})


# ==============================
# CHAT HISTORY API ENDPOINTS
# ==============================

@api_view(['GET'])
def get_chat_history(request):
    """
    Ambil riwayat chat pengguna (percakapan).
    Returns list of recent conversations for the logged-in user.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed. Gunakan GET."}, status=405)
    
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
        logger.error("get_chat_history_error", extra={"error": str(e)})
        return JsonResponse({"error": "Internal server error"}, status=500)


def get_conversation_messages(request, conversation_id):
    """
    Get all messages dari specific conversation.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed. Gunakan GET."}, status=405)
    
    try:
        from apps.chatbot.models import Conversation, Message
        conversation = Conversation.objects.get(id=conversation_id)
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')
        
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'conversation': {
                'id': conversation.id,
                'title': conversation.title,
                'created_at': conversation.created_at.isoformat(),
                'updated_at': conversation.updated_at.isoformat()
            },
            'messages': messages_data
        })
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)
    except Exception as e:
        logger.error("get_conversation_messages_error", extra={"error": str(e), "conversation_id": conversation_id})
        return JsonResponse({"error": "Gagal mengambil messages.", "detail": str(e)}, status=500)


@api_view(['POST'])
@csrf_exempt
def send_message(request, conversation_id):
    """
    Kirim pesan baru ke percakapan yang sudah ada via DRF API Endpoint.
    """
    content = request.data.get('content')
    session_id = request.data.get('session_id')
    user_id = request.data.get('user_id')

    if not content:
        return Response({"error": "Content is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from apps.chatbot.models import Conversation, Message
        
        Message.objects.create(
            conversation_id=conversation_id,
            role="user",
            content=content
        )

        chat_fn = _get_chat_fn()
        vector_store, embedding_service = _get_rag_dependencies()
        actual_session_id = session_id or f"conv_{conversation_id}"
        # new_session resets stale state when caller explicitly requests it.
        # Default False: mid-conversation messages continue the same session.
        new_session_flag = bool(request.data.get("new_session", False))

        answer = chat_fn(
            question=content,
            vector_store=vector_store,
            embedding_service=embedding_service,
            session_id=actual_session_id,
            new_session=new_session_flag,
        )

        Message.objects.create(
            conversation_id=conversation_id,
            role="assistant",
            content=answer
        )

        messages = Message.objects.filter(conversation_id=conversation_id).order_by('created_at')
        return Response({
            "success": True,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ]
        })

    except Exception as e:
        logger.error("send_message_error", extra={"error": str(e)})
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)