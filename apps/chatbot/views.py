from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

import json
import ollama

from .models import Conversation, Message, ChatSession, UINavigatorMap
from .serializers import (
    ConversationSerializer,
    ConversationListSerializer,
    MessageSerializer
)
from apps.rag.services.chat_service import SYSTEM_RULE_CONTENT, DISCLAIMER, _FALLBACK_SYSTEM_PROMPT


def _get_rag_dependencies():
    """Ambil vector_store dan embedding_service dari singleton."""
    from apps.rag.apps import get_vector_store, get_embedding_service
    return get_vector_store(), get_embedding_service()


def _get_relevant_context(query: str, vector_store, embedding_service, similarity_threshold=0.35):
    """Simple RAG retrieval untuk check apakah ada SOP yang relevan."""
    if not vector_store or not embedding_service:
        return None
    
    try:
        query_embedding = embedding_service.embed([query])[0]
        results, distances = vector_store.search_similar(query_embedding, top_k=3)
        
        # Check jika ada hasil dengan similarity score di atas threshold
        if results and len(results) > 0:
            best_distance = distances[0] if isinstance(distances, (list, tuple)) else distances
            if best_distance > similarity_threshold:
                return "\n".join(results)
        return None
    except Exception:
        return None

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
            {"role": "system", "content": "Anda adalah classifier masalah IT yang sangat ahli. WAJIB gunakan Bahasa Indonesia."},
            {"role": "user", "content": prompt}
        ],
        options={"temperature": 0}
    )

    return response["message"]["content"].strip()


# ==============================
# CHAT TEMPLATE VIEW
# ==============================

def chat_view(request):
    """❌ DEPRECATED - use chat_page instead"""
    return render(request, 'chatbot/chat.html', {
        "conversations": [],
        "messages": []
    })


def chat_page(request):
    """
    Render main chat page
    ✅ PROTECTED: Requires user to be authenticated
    Redirects to login if user is not logged in
    """
    from apps.users.decorators import login_required_redirect
    
    @login_required_redirect
    def _chat_page(request):
        # Load user-specific data
        user = request.user
        conversations = []
        
        if user.is_authenticated:
            # Fetch user's conversations
            from .models import Conversation
            conversations = Conversation.objects.filter(
                user=user
            ).order_by('-created_at')[:10]
        
        return render(request, 'chatbot/chat.html', {
            "user": user,
            "conversations": conversations,
        })
    
    return _chat_page(request)


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

            # Cek apakah ada SOP yang relevan (RAG retrieval)
            vector_store, embedding_service = _get_rag_dependencies()
            context = _get_relevant_context(content, vector_store, embedding_service)
            
            # Build system prompt berdasarkan ada/tidaknya SOP
            if context:
                system_prompt = (
                    "Anda adalah SITI, AI IT Support tingkat L1 di perusahaan.\n\n"
                    f"KONTEKS SOP RESMI:\n{context}\n\n"
                    "Ikuti panduan SOP di atas dengan KETAT dan PERSIS."
                )
            else:
                system_prompt = _FALLBACK_SYSTEM_PROMPT

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": 0.3}
            )

            answer = response["message"]["content"]
            
            # Tambahkan disclaimer jika tidak ada SOP
            if not context:
                answer = DISCLAIMER + answer

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
        """Archive endpoint - returns success without action (field removed)"""

        return Response(
            {'detail': 'Archive functionality has been removed'},
            status=status.HTTP_200_OK
        )

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
            # Cek apakah ada SOP yang relevan (RAG retrieval)
            vector_store, embedding_service = _get_rag_dependencies()
            context = _get_relevant_context(query, vector_store, embedding_service)
            
            # Build system prompt berdasarkan ada/tidaknya SOP
            if context:
                system_prompt = (
                    "Anda adalah SITI, AI IT Support tingkat L1 di perusahaan.\n\n"
                    f"KONTEKS SOP RESMI:\n{context}\n\n"
                    "Ikuti panduan SOP di atas dengan KETAT dan PERSIS."
                )
            else:
                system_prompt = _FALLBACK_SYSTEM_PROMPT
                # Yield disclaimer dulu jika tidak ada SOP
                yield DISCLAIMER

            stream = ollama.chat(
                model="llama3:8b",
                messages=[
                    {"role": "system", "content": system_prompt},
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