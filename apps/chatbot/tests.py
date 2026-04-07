import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.chatbot.models import Conversation, Message


@pytest.mark.django_db
class TestConversationAPI:
    """Test Chatbot Conversation API"""

    def setup_method(self):
        """Setup test fixtures"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_create_conversation(self):
        """Test creating a new conversation"""
        data = {'title': 'Test Conversation'}
        response = self.client.post('/api/v1/chatbot/conversations/', data)
        assert response.status_code == 201
        assert response.data['title'] == 'Test Conversation'

    def test_list_conversations(self):
        """Test listing conversations"""
        Conversation.objects.create(
            user=self.user,
            title='Test Conv 1'
        )
        Conversation.objects.create(
            user=self.user,
            title='Test Conv 2'
        )
        response = self.client.get('/api/v1/chatbot/conversations/')
        assert response.status_code == 200
        assert len(response.data['results']) == 2

    def test_send_message(self):
        """Test sending a message"""
        conv = Conversation.objects.create(
            user=self.user,
            title='Test Conversation'
        )
        data = {'content': 'Hello, how can I help?'}
        response = self.client.post(
            f'/api/v1/chatbot/conversations/{conv.id}/send_message/',
            data
        )
        assert response.status_code == 201
        assert conv.messages.count() == 2  # user + assistant

    def test_archive_conversation(self):
        """Test archiving a conversation"""
        conv = Conversation.objects.create(
            user=self.user,
            title='Test Conversation'
        )
        response = self.client.post(
            f'/api/v1/chatbot/conversations/{conv.id}/archive/'
        )
        assert response.status_code == 200
