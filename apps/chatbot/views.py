from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import render
from .models import Conversation, Message
from .serializers import ConversationSerializer, ConversationListSerializer, MessageSerializer
from django.shortcuts import render

def chat_view(request):
    return render(request, 'chatbot/chat.html', {
        "conversations": [],
        "messages": []
    })

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
        """Send a message to the chatbot"""
        conversation = self.get_object()
        
        content = request.data.get('content')
        if not content:
            return Response(
                {'error': 'Content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save user message
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content
        )

        # TODO: Generate AI response using RAG
        # For now, return a placeholder response
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='This is a placeholder response. Implement RAG logic here.'
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


# Template Views
def chat_page(request):
    """Render main chat page"""
    return render(request, 'chatbot/chat.html')
