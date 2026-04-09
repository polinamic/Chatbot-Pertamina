"""
API endpoint tests
Tests REST API endpoints, serialization, and error handling
"""
import pytest
import json
from rest_framework.test import APIClient
from django.urls import reverse
from apps.chatbot.models import Conversation, Message


@pytest.fixture
def api_client():
    """Return API client"""
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, test_user_with_profile_and_settings):
    """Return authenticated API client"""
    api_client.force_authenticate(user=test_user_with_profile_and_settings)
    return api_client


@pytest.mark.django_db(transaction=True)
class TestConversationAPI:
    """Test Conversation API endpoints"""
    
    def test_list_conversations_authenticated(self, authenticated_api_client, test_user):
        """Test listing conversations requires authentication"""
        response = authenticated_api_client.get('/api/v1/conversations/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
    
    def test_list_conversations_unauthenticated(self, api_client):
        """Test listing conversations without auth returns 401"""
        response = api_client.get('/api/v1/conversations/')
        
        assert response.status_code == 401
    
    def test_list_only_user_conversations(self, authenticated_api_client, test_user):
        """Test user only sees their own conversations"""
        # Create conversations for this user
        Conversation.objects.create(user=test_user, title='User Conv')
        
        # Create conversation for different user
        from tests.factories import UserFactory
        other_user = UserFactory()
        Conversation.objects.create(user=other_user, title='Other Conv')
        
        response = authenticated_api_client.get('/api/v1/conversations/')
        
        # Should only see user's conversation
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'User Conv'
    
    def test_create_conversation(self, authenticated_api_client, test_user):
        """Test creating a new conversation"""
        data = {'title': 'New Chat'}
        response = authenticated_api_client.post('/api/v1/conversations/', data)
        
        assert response.status_code == 201
        assert Conversation.objects.filter(user=test_user, title='New Chat').exists()
    
    def test_create_conversation_requires_auth(self, api_client):
        """Test creating conversation without auth returns 401"""
        response = api_client.post('/api/v1/conversations/', {'title': 'New'})
        
        assert response.status_code == 401
    
    def test_retrieve_conversation(self, authenticated_api_client, test_conversation):
        """Test retrieving a specific conversation"""
        response = authenticated_api_client.get(f'/api/v1/conversations/{test_conversation.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == test_conversation.id
        assert response.data['title'] == test_conversation.title
    
    def test_cannot_retrieve_other_user_conversation(self, authenticated_api_client):
        """Test cannot access other user's conversation"""
        from tests.factories import ConversationFactory
        
        other_conv = ConversationFactory()
        response = authenticated_api_client.get(f'/api/v1/conversations/{other_conv.id}/')
        
        # Should be forbidden
        assert response.status_code in [403, 404]
    
    def test_update_conversation(self, authenticated_api_client, test_conversation):
        """Test updating conversation"""
        data = {'title': 'Updated Title'}
        response = authenticated_api_client.patch(
            f'/api/v1/conversations/{test_conversation.id}/',
            data
        )
        
        assert response.status_code == 200
        test_conversation.refresh_from_db()
        assert test_conversation.title == 'Updated Title'
    
    def test_delete_conversation(self, authenticated_api_client, test_conversation):
        """Test deleting conversation"""
        conv_id = test_conversation.id
        response = authenticated_api_client.delete(
            f'/api/v1/conversations/{conv_id}/'
        )
        
        assert response.status_code == 204
        assert not Conversation.objects.filter(id=conv_id).exists()


@pytest.mark.django_db(transaction=True)
class TestMessageAPI:
    """Test Message API endpoints"""
    
    def test_send_message_creates_record(self, authenticated_api_client, test_conversation):
        """Test sending message via API"""
        data = {'content': 'Hello chatbot'}
        response = authenticated_api_client.post(
            f'/api/v1/conversations/{test_conversation.id}/send_message/',
            data
        )
        
        assert response.status_code in [200, 201]
        assert Message.objects.filter(
            conversation=test_conversation,
            content='Hello chatbot'
        ).exists()
    
    def test_send_message_requires_conversation_ownership(self, authenticated_api_client):
        """Test cannot send message to other user's conversation"""
        from tests.factories import ConversationFactory
        
        other_conv = ConversationFactory()
        data = {'content': 'Hacked'}
        response = authenticated_api_client.post(
            f'/api/v1/conversations/{other_conv.id}/send_message/',
            data
        )
        
        assert response.status_code in [403, 404]
    
    def test_get_conversation_messages(self, authenticated_api_client, test_conversation_with_messages):
        """Test retrieving messages"""
        response = authenticated_api_client.get(
            f'/api/v1/conversations/{test_conversation_with_messages.id}/messages/'
        )
        
        assert response.status_code == 200
        assert len(response.data) == 2
    
    def test_message_ordering(self, authenticated_api_client, test_conversation):
        """Test messages are ordered chronologically"""
        # Create messages
        msg1 = Message.objects.create(conversation=test_conversation, role='user', content='First')
        msg2 = Message.objects.create(conversation=test_conversation, role='assistant', content='Second')
        msg3 = Message.objects.create(conversation=test_conversation, role='user', content='Third')
        
        response = authenticated_api_client.get(
            f'/api/v1/conversations/{test_conversation.id}/messages/'
        )
        
        # Should be in chronological order
        assert response.data[0]['content'] == 'First'
        assert response.data[1]['content'] == 'Second'
        assert response.data[2]['content'] == 'Third'


@pytest.mark.django_db(transaction=True)
class TestUserAPI:
    """Test User/Profile API endpoints"""
    
    def test_get_current_user_profile(self, authenticated_api_client, test_user):
        """Test getting current user profile"""
        response = authenticated_api_client.get('/api/v1/users/profile/')
        
        assert response.status_code == 200
        assert response.data['username'] == 'testuser'
    
    def test_update_user_profile(self, authenticated_api_client, test_user):
        """Test updating user profile"""
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '08123456789'
        }
        response = authenticated_api_client.patch('/api/v1/users/profile/', data)
        
        assert response.status_code == 200
        test_user.refresh_from_db()
        assert test_user.first_name == 'Updated'
    
    def test_cannot_see_other_user_profile(self, authenticated_api_client):
        """Test cannot access other user's profile"""
        from tests.factories import UserFactory
        
        other_user = UserFactory(username='otheruser')
        response = authenticated_api_client.get(f'/api/v1/users/{other_user.id}/')
        
        assert response.status_code in [403, 404]


@pytest.mark.django_db(transaction=True)
class TestSettingsAPI:
    """Test Settings API endpoints"""
    
    def test_get_user_settings(self, authenticated_api_client, test_user):
        """Test getting user settings"""
        response = authenticated_api_client.get('/api/v1/users/settings/')
        
        assert response.status_code == 200
        assert 'theme' in response.data
        assert 'language' in response.data
    
    def test_update_user_settings(self, authenticated_api_client, test_user):
        """Test updating user settings"""
        data = {
            'theme': 'dark',
            'language': 'en',
            'enable_notifications': False
        }
        response = authenticated_api_client.patch('/api/v1/users/settings/', data)
        
        assert response.status_code == 200
        test_user.settings.refresh_from_db()
        assert test_user.settings.theme == 'dark'
        assert test_user.settings.language == 'en'
    
    def test_cannot_update_other_user_settings(self, authenticated_api_client):
        """Test cannot update other user's settings"""
        from tests.factories import UserFactory
        
        other_user = UserFactory()
        data = {'theme': 'dark'}
        response = authenticated_api_client.patch(
            f'/api/v1/users/{other_user.id}/settings/',
            data
        )
        
        # Should be forbidden or not found
        assert response.status_code in [403, 404]
        
        # Other user's settings should not change
        other_user.settings.refresh_from_db()
        assert other_user.settings.theme != 'dark'


@pytest.mark.django_db(transaction=True)
class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_404_for_nonexistent_conversation(self, authenticated_api_client):
        """Test 404 for nonexistent conversation"""
        response = authenticated_api_client.get('/api/v1/conversations/99999/')
        
        assert response.status_code == 404
    
    def test_400_for_invalid_data(self, authenticated_api_client):
        """Test 400 for invalid data"""
        # Missing required field
        response = authenticated_api_client.post('/api/v1/conversations/', {})
        
        assert response.status_code == 400
    
    def test_401_without_authentication(self, api_client):
        """Test 401 when not authenticated"""
        response = api_client.get('/api/v1/conversations/')
        
        assert response.status_code == 401
    
    def test_405_for_invalid_method(self, authenticated_api_client):
        """Test 405 for invalid HTTP method"""
        response = authenticated_api_client.delete('/api/v1/conversations/')
        
        assert response.status_code == 405


@pytest.mark.django_db(transaction=True)
class TestAPIResponseFormat:
    """Test API response format consistency"""
    
    def test_conversation_response_structure(self, authenticated_api_client, test_conversation):
        """Test conversation response has correct structure"""
        response = authenticated_api_client.get(f'/api/v1/conversations/{test_conversation.id}/')
        
        required_fields = ['id', 'user', 'title', 'created_at', 'is_archived']
        for field in required_fields:
            assert field in response.data
    
    def test_message_response_structure(self, authenticated_api_client, test_conversation_with_messages):
        """Test message response has correct structure"""
        response = authenticated_api_client.get(
            f'/api/v1/conversations/{test_conversation_with_messages.id}/messages/'
        )
        
        if response.data:
            required_fields = ['id', 'conversation', 'role', 'content', 'created_at']
            for field in required_fields:
                assert field in response.data[0]
    
    def test_user_settings_response_structure(self, authenticated_api_client):
        """Test settings response has correct structure"""
        response = authenticated_api_client.get('/api/v1/users/settings/')
        
        required_fields = ['theme', 'language', 'enable_notifications']
        for field in required_fields:
            assert field in response.data
