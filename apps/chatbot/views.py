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