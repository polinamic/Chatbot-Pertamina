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

# Model & serializer chatbot ada di app terpisah
from apps.chatbot.models import Conversation, Message, ChatSession, UINavigatorMap
from apps.chatbot.serializers import (
    ConversationSerializer,
    ConversationListSerializer,
    MessageSerializer,
)

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
            is_processed=False,
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
# CONVERSATION VIEWSET
# ==============================

class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk mengelola conversations
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """
        Send message dengan Agentic Workflow
        """

        conversation = self.get_object()
        content = request.data.get('content')

        if not content:
            return Response(
                {'error': 'Content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # =============================
        # SAVE USER MESSAGE
        # =============================

        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content
        )

        # =============================
        # GET OR CREATE CHAT SESSION
        # =============================

        session, created = ChatSession.objects.get_or_create(
            conversation=conversation,
            defaults={"user": conversation.user}
        )

        # =============================
        # DETECT NEGATIVE RESPONSE
        # =============================

        if is_negative_response(content):
            session.failure_count += 1
            session.save()

        # =============================
        # PHASE 1: NORMAL RAG
        # =============================

        if session.failure_count < 3:

            prompt = f"""
User bertanya:

{content}

Berikan solusi troubleshooting IT.

Di akhir jawaban WAJIB bertanya:

"Apakah solusi ini menyelesaikan masalah Anda?"
"""

            response = ollama.chat(
                model="llama3:8b",
                messages=[
                    {"role": "system", "content": "Anda adalah IT Support perusahaan."},
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": 0.3}
            )

            answer = response["message"]["content"]

        else:

            # =============================
            # PHASE 2: UI ESCALATION
            # =============================

            category = classify_ui_category(content)

            try:

                ui_map = UINavigatorMap.objects.get(
                    category_name=category
                )

                answer = f"""
Sepertinya saya perlu bantuan teknisi.

Silakan ikuti langkah berikut di layar Anda untuk membuat tiket:

{ui_map.ui_steps}
"""

            except UINavigatorMap.DoesNotExist:

                answer = """
Sepertinya masalah perlu ditangani teknisi.

Silakan buka portal IT Support dan buat tiket baru.
"""

        # =============================
        # SAVE ASSISTANT MESSAGE
        # =============================

        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=answer
        )

        serializer = ConversationSerializer(conversation)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a conversation"""

        conversation = self.get_object()

        conversation.is_archived = True
        conversation.save()

        serializer = self.get_serializer(conversation)

        return Response(serializer.data)


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
    
    PERBAIKAN 7: Menyimpan chat history ke database.
    - Frontend mengirim user_id
    - Endpoint membuat/mendapatkan Conversation
    - Menyimpan user message dan bot answer ke Message model
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
    user_id = body.get("user_id")

    if not query:
        return JsonResponse({"error": "Field 'query' wajib diisi."}, status=400)

    # --- Get or create conversation for user ---
    conversation = None
    if user_id:
        try:
            from django.contrib.auth.models import User
            from apps.chatbot.models import Conversation, Message
            
            user = User.objects.get(id=user_id)
            # Ambil conversation terbaru, atau buat baru jika tidak ada
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

<<<<<<< Updated upstream
    return JsonResponse({"answer": answer, "session_id": session_id})
=======
    # --- Simpan pesan ke database jika user terautentikasi ---
    if conversation:
        try:
            from apps.chatbot.models import Message
            # Simpan user message
            Message.objects.create(
                conversation=conversation,
                role='user',
                content=query
            )
            # Simpan bot answer
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=answer
            )
            # Update conversation title jika masih default
            if conversation.title == query[:50] + ("..." if len(query) > 50 else ""):
                conversation.title = query[:100] + ("..." if len(query) > 100 else "")
                conversation.save()
        except Exception as e:
            logger.error("siti_chat_save_message_error", extra={"error": str(e), "user_id": user_id})

    return JsonResponse({"answer": answer, "session_id": session_id})


# ==============================
# GET CONVERSATION MESSAGES
# ==============================
def get_conversation_messages(request, conversation_id):
    """
    Get all messages dari specific conversation.
    Frontend gunakan endpoint ini untuk load chat history saat user klik conversation di sidebar.
    
    GET /api/v1/rag/conversation/<conversation_id>/messages/
    
    Response:
    {
        "success": true,
        "conversation": {
            "id": 1,
            "title": "...",
            "created_at": "...",
            "updated_at": "..."
        },
        "messages": [
            {
                "id": 1,
                "role": "user",
                "content": "...",
                "created_at": "..."
            },
            ...
        ]
    }
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed. Gunakan GET."}, status=405)
    
    try:
        from apps.chatbot.models import Conversation, Message
        
        # Get conversation
        conversation = Conversation.objects.get(id=conversation_id)
        
        # Get all messages dalam conversation, ordered by created_at
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')
        
        # Build response
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
        return JsonResponse({
            "error": "Conversation not found"
        }, status=404)
    except Exception as e:
        logger.error("get_conversation_messages_error", extra={"error": str(e), "conversation_id": conversation_id})
        return JsonResponse({
            "error": "Gagal mengambil messages.",
            "detail": str(e)
        }, status=500)


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
>>>>>>> Stashed changes
