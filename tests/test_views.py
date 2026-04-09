"""
View/Integration tests
Tests views, templates, and form processing
"""
import pytest
import json
from django.urls import reverse
from django.test import Client
from apps.chatbot.models import Conversation, Message


@pytest.mark.django_db(transaction=True)
class TestChatPageView:
    """Test chat page view"""
    
    def test_chat_page_loads_for_authenticated_user(self, authenticated_client):
        """Test chat page renders for authenticated user"""
        response = authenticated_client.get('/chatbot/')
        
        assert response.status_code == 200
        assert 'chat' in response.content.decode().lower()
    
    def test_chat_page_shows_conversations_list(self, authenticated_client, test_user):
        """Test chat page displays user's conversations"""
        # Create conversations for user
        Conversation.objects.create(user=test_user, title='First Chat')
        Conversation.objects.create(user=test_user, title='Second Chat')
        
        response = authenticated_client.get('/chatbot/')
        content = response.content.decode()
        
        # Should show conversation titles
        assert 'First Chat' in content or 'First Chat' in content.lower()
    
    def test_chat_page_has_message_form(self, authenticated_client):
        """Test chat page has message input form"""
        response = authenticated_client.get('/chatbot/')
        content = response.content.decode()
        
        # Should have input field or textarea
        assert 'input' in content.lower() or 'textarea' in content.lower()
    
    def test_chat_page_has_new_chat_button(self, authenticated_client):
        """Test chat page has 'new chat' button"""
        response = authenticated_client.get('/chatbot/')
        content = response.content.decode()
        
        # Should have button to create new chat
        assert 'button' in content.lower() or 'new' in content.lower()
    
    def test_redirect_to_login_when_not_authenticated(self, client):
        """Test redirect to login when accessing chat without auth"""
        response = client.get('/chatbot/', follow=True)
        
        # Should redirect to login
        assert 'login' in response.request['PATH_INFO'].lower()


@pytest.mark.django_db(transaction=True)
class TestProfilePageView:
    """Test profile page view"""
    
    def test_profile_page_loads_for_authenticated_user(self, authenticated_client):
        """Test profile page renders"""
        response = authenticated_client.get('/auth/profile/')
        
        assert response.status_code == 200
    
    def test_profile_page_shows_user_info(self, authenticated_client, test_user_with_profile_and_settings):
        """Test profile page displays user information"""
        response = authenticated_client.get('/auth/profile/')
        content = response.content.decode()
        
        # Should contain profile fields
        assert 'email' in content.lower() or test_user_with_profile_and_settings.email in content
    
    def test_profile_page_has_edit_form(self, authenticated_client):
        """Test profile page has edit form"""
        response = authenticated_client.get('/auth/profile/')
        content = response.content.decode()
        
        # Should have form to edit profile
        assert 'form' in content.lower() or 'input' in content.lower()
    
    def test_profile_update_success(self, authenticated_client, test_user_with_profile_and_settings):
        """Test successful profile update"""
        update_data = {
            'first_name': 'Updated',
            'last_name': 'User',
            'phone': '08199999999',
            'company': 'Pertamina Updated',
            'department': 'Finance'
        }
        
        response = authenticated_client.post('/auth/profile/', update_data, follow=True)
        
        # Verify update
        test_user_with_profile_and_settings.refresh_from_db()
        assert test_user_with_profile_and_settings.first_name == 'Updated'
        assert test_user_with_profile_and_settings.profile.phone == '08199999999'
    
    def test_profile_page_redirects_if_not_authenticated(self, client):
        """Test profile page redirects when not authenticated"""
        response = client.get('/auth/profile/', follow=True)
        
        assert 'login' in response.request['PATH_INFO'].lower()
    
    def test_cannot_edit_other_user_profile(self, authenticated_client, test_user):
        """Test user cannot edit another user's profile"""
        # Create another user
        from tests.factories import UserFactory
        other_user = UserFactory()
        
        # Try to update other user's profile
        update_data = {
            'first_name': 'Hacker',
            'user_id': other_user.id  # Trying to change someone else's profile
        }
        
        response = authenticated_client.post('/auth/profile/', update_data)
        
        # Other user's profile should not change
        other_user.refresh_from_db()
        assert other_user.first_name != 'Hacker'


@pytest.mark.django_db(transaction=True)
class TestSettingsPageView:
    """Test settings page view"""
    
    def test_settings_page_loads_for_authenticated_user(self, authenticated_client):
        """Test settings page renders"""
        response = authenticated_client.get('/auth/settings/')
        
        assert response.status_code == 200
    
    def test_settings_page_shows_settings(self, authenticated_client, test_user_with_profile_and_settings):
        """Test settings page displays user settings"""
        response = authenticated_client.get('/auth/settings/')
        content = response.content.decode()
        
        # Should show settings options
        assert 'theme' in content.lower() or 'language' in content.lower()
    
    def test_settings_page_has_edit_form(self, authenticated_client):
        """Test settings page has form"""
        response = authenticated_client.get('/auth/settings/')
        content = response.content.decode()
        
        # Should have form to update settings
        assert 'form' in content.lower() or 'select' in content.lower() or 'input' in content.lower()
    
    def test_settings_update_theme(self, authenticated_client, test_user):
        """Test updating theme setting"""
        update_data = {
            'theme': 'dark',
            'language': 'id',
            'enable_notifications': True
        }
        
        response = authenticated_client.post('/auth/settings/', update_data)
        
        # Verify update
        test_user.settings.refresh_from_db()
        assert test_user.settings.theme == 'dark'
    
    def test_settings_update_language(self, authenticated_client, test_user):
        """Test updating language setting"""
        update_data = {
            'theme': 'light',
            'language': 'en',
            'enable_notifications': True
        }
        
        response = authenticated_client.post('/auth/settings/', update_data)
        
        # Verify update
        test_user.settings.refresh_from_db()
        assert test_user.settings.language == 'en'
    
    def test_settings_update_notifications(self, authenticated_client, test_user):
        """Test enabling/disabling notifications"""
        update_data = {
            'theme': 'light',
            'language': 'id',
            'enable_notifications': False
        }
        
        response = authenticated_client.post('/auth/settings/', update_data)
        
        # Verify update
        test_user.settings.refresh_from_db()
        assert test_user.settings.enable_notifications is False
    
    def test_settings_page_redirects_if_not_authenticated(self, client):
        """Test settings page redirects when not authenticated"""
        response = client.get('/auth/settings/', follow=True)
        
        assert 'login' in response.request['PATH_INFO'].lower()
    
    def test_cannot_edit_other_user_settings(self, authenticated_client, test_user):
        """Test user cannot edit another user's settings"""
        from tests.factories import UserFactory
        other_user = UserFactory()
        
        # Try to update other user's settings
        update_data = {
            'theme': 'dark',
            'user_id': other_user.id  # Trying to change someone else's settings
        }
        
        response = authenticated_client.post('/auth/settings/', update_data)
        
        # Other user's settings should not change
        other_user.settings.refresh_from_db()
        assert other_user.settings.theme != 'dark'


@pytest.mark.django_db(transaction=True)
class TestConversationManagement:
    """Test conversation creation and management"""
    
    def test_create_new_conversation(self, authenticated_client, test_user):
        """Test creating a new conversation"""
        response = authenticated_client.post('/api/v1/conversations/', {
            'title': 'New Conversation'
        }, content_type='application/json')
        
        # Conversation should be created
        assert Conversation.objects.filter(user=test_user, title='New Conversation').exists()
    
    def test_list_user_conversations(self, authenticated_client, test_user):
        """Test getting list of user's conversations"""
        # Create conversations
        Conversation.objects.create(user=test_user, title='Conv 1')
        Conversation.objects.create(user=test_user, title='Conv 2')
        
        response = authenticated_client.get('/api/v1/conversations/')
        
        # Should list user's conversations
        assert response.status_code == 200
    
    def test_get_specific_conversation(self, authenticated_client, test_conversation):
        """Test getting a specific conversation"""
        response = authenticated_client.get(f'/api/v1/conversations/{test_conversation.id}/')
        
        assert response.status_code == 200
    
    def test_cannot_access_other_user_conversation(self, authenticated_client, test_user):
        """Test user cannot access other user's conversation"""
        from tests.factories import ConversationFactory
        
        other_conv = ConversationFactory()  # Belongs to different user
        
        response = authenticated_client.get(f'/api/v1/conversations/{other_conv.id}/')
        
        # Should be 404 or 403
        assert response.status_code in [404, 403]
    
    def test_archive_conversation(self, authenticated_client, test_conversation):
        """Test archiving a conversation"""
        response = authenticated_client.post(
            f'/api/v1/conversations/{test_conversation.id}/archive/',
            content_type='application/json'
        )
        
        test_conversation.refresh_from_db()
        assert test_conversation.is_archived is True


@pytest.mark.django_db(transaction=True)
class TestMessageHandling:
    """Test message creation and retrieval"""
    
    def test_send_message_creates_record(self, authenticated_client, test_conversation, test_user):
        """Test sending message creates database record"""
        response = authenticated_client.post(
            f'/api/v1/conversations/{test_conversation.id}/send_message/',
            {'content': 'Test message'},
            content_type='application/json'
        )
        
        # Message should be created
        assert Message.objects.filter(
            conversation=test_conversation,
            content='Test message'
        ).exists()
    
    def test_get_conversation_messages(self, authenticated_client, test_conversation_with_messages):
        """Test retrieving messages from conversation"""
        response = authenticated_client.get(
            f'/api/v1/conversations/{test_conversation_with_messages.id}/messages/'
        )
        
        assert response.status_code == 200
        # Response should contain messages
        data = response.json() if hasattr(response, 'json') else json.loads(response.content)
        assert len(data) >= 2
    
    def test_message_user_isolation(self, authenticated_client, test_user):
        """Test messages are isolated per user"""
        from tests.factories import ConversationFactory
        
        # Create conversation for different user
        other_conv = ConversationFactory()
        Message.objects.create(
            conversation=other_conv,
            role='user',
            content='Other user message'
        )
        
        # Current user should not see other user's message
        response = authenticated_client.get('/api/v1/messages/')
        
        # Response should only contain current user's messages
        data = response.json() if hasattr(response, 'json') else json.loads(response.content)
        for msg in data:
            assert msg['conversation']['user_id'] == test_user.id
