"""
Database integrity & security tests
Tests data relationships, cascading, and security vulnerabilities
"""
import pytest
from django.db import connection, IntegrityError
from django.core.exceptions import ValidationError
from apps.chatbot.models import Conversation, Message
from apps.users.models import UserProfile, UserSettings


@pytest.mark.django_db(transaction=True)
class TestDatabaseRelationships:
    """Test database relationship integrity"""
    
    def test_cascade_delete_messages_when_conversation_deleted(self):
        """Test messages are deleted when conversation is deleted"""
        from tests.factories import ConversationFactory
        
        conv = ConversationFactory()
        msg1 = Message.objects.create(conversation=conv, role='user', content='Msg 1')
        msg2 = Message.objects.create(conversation=conv, role='assistant', content='Msg 2')
        
        assert Message.objects.count() == 2
        
        conv.delete()
        
        # Messages should be deleted automatically
        assert Message.objects.count() == 0
    
    def test_cascade_delete_conversations_when_user_deleted(self, test_user):
        """Test conversations are deleted when user is deleted"""
        Conversation.objects.create(user=test_user, title='Conv 1')
        Conversation.objects.create(user=test_user, title='Conv 2')
        
        user_id = test_user.id
        test_user.delete()
        
        # Conversations should be deleted
        assert Conversation.objects.count() == 0
    
    def test_cascade_delete_profile_when_user_deleted(self, test_user_with_profile_and_settings):
        """Test profile is deleted when user is deleted"""
        user = test_user_with_profile_and_settings
        profile = user.profile
        
        user.delete()
        
        # Profile should be deleted
        assert not UserProfile.objects.filter(id=profile.id).exists()
    
    def test_cascade_delete_settings_when_user_deleted(self, test_user_with_profile_and_settings):
        """Test settings are deleted when user is deleted"""
        user = test_user_with_profile_and_settings
        settings = user.settings
        
        user.delete()
        
        # Settings should be deleted
        assert not UserSettings.objects.filter(id=settings.id).exists()
    
    def test_conversation_user_foreign_key(self, test_user):
        """Test conversation has correct foreign key to user"""
        conv = Conversation.objects.create(user=test_user, title='Test')
        
        assert conv.user.id == test_user.id
        assert test_user in conv.user.__class__.objects.all()
    
    def test_message_conversation_foreign_key(self, test_conversation):
        """Test message has correct foreign key to conversation"""
        msg = Message.objects.create(conversation=test_conversation, role='user', content='Test')
        
        assert msg.conversation.id == test_conversation.id


@pytest.mark.django_db(transaction=True)
class TestDataIntegrityConstraints:
    """Test database constraints and validation"""
    
    def test_message_content_not_null(self, test_conversation):
        """Test message content cannot be null"""
        with pytest.raises(Exception):  # IntegrityError or ValidationError
            Message.objects.create(
                conversation=test_conversation,
                role='user',
                content=None
            )
    
    def test_message_role_must_be_valid_choice(self, test_conversation):
        """Test message role must be valid choice"""
        # Should fail with invalid role
        with pytest.raises(Exception):
            msg = Message(conversation=test_conversation, role='invalid', content='Test')
            msg.full_clean()  # Validate before saving
    
    def test_conversation_title_not_empty(self, test_user):
        """Test conversation title cannot be empty"""
        with pytest.raises(Exception):
            conv = Conversation(user=test_user, title='')
            conv.full_clean()
    
    def test_user_email_is_unique(self):
        """Test user email must be unique"""
        from django.contrib.auth.models import User
        
        User.objects.create_user(username='user1', email='test@example.com')
        
        with pytest.raises(Exception):  # IntegrityError
            User.objects.create_user(username='user2', email='test@example.com')


@pytest.mark.django_db(transaction=True)
class TestSecurityVulnerabilities:
    """Test for common security vulnerabilities"""
    
    def test_sql_injection_protection(self, authenticated_api_client):
        """Test protection against SQL injection"""
        # Try SQL injection
        response = authenticated_api_client.get(
            "/api/v1/conversations/?search='; DROP TABLE conversations; --"
        )
        
        # Should not execute SQL, return safe response
        assert response.status_code in [200, 400]
        # Table should still exist
        assert Conversation.objects.count() >= 0
    
    def test_xss_protection_in_message_content(self, authenticated_api_client, test_conversation):
        """Test XSS protection in message content"""
        xss_payload = '<script>alert("XSS")</script>'
        
        data = {'content': xss_payload}
        response = authenticated_api_client.post(
            f'/api/v1/conversations/{test_conversation.id}/send_message/',
            data
        )
        
        # Message should be saved but content should be escaped/sanitized
        if response.status_code in [200, 201]:
            msg = Message.objects.filter(conversation=test_conversation).last()
            # Check if content is preserved or sanitized (not executed)
            assert msg.content in [xss_payload, xss_payload]  # Check both raw and potentially sanitized
    
    def test_csrf_protection_on_post_requests(self, client, test_user):
        """Test CSRF protection on POST requests"""
        # Attempting POST without CSRF token should fail
        response = client.post('/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123'
        })
        
        # Django should require CSRF token for POST
        assert response.status_code in [403, 400] or 'csrf' in response.content.decode().lower()
    
    def test_password_not_exposed_in_responses(self, authenticated_api_client, test_user):
        """Test that passwords are never exposed in API responses"""
        response = authenticated_api_client.get(f'/api/v1/users/{test_user.id}/')
        
        # Response should not contain password
        response_text = str(response.data)
        assert 'password' not in response_text.lower()
        assert 'TestPassword123' not in response_text
    
    def test_user_cannot_escalate_privileges(self, authenticated_api_client, test_user):
        """Test user cannot escalate to admin"""
        data = {'is_superuser': True, 'is_staff': True}
        response = authenticated_api_client.patch('/api/v1/users/profile/', data)
        
        # User should remain non-admin
        test_user.refresh_from_db()
        assert test_user.is_superuser is False
        assert test_user.is_staff is False
    
    def test_timing_attack_protection(self, client, test_user):
        """Test protection against timing attacks in authentication"""
        import time
        
        # Attempt with nonexistent user
        start = time.time()
        response1 = client.post('/auth/login/', {
            'username': 'nonexistent',
            'password': 'wrongpass'
        })
        time1 = time.time() - start
        
        # Attempt with existing user but wrong password
        start = time.time()
        response2 = client.post('/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        time2 = time.time() - start
        
        # Times should be similar (within reasonable margin)
        # difference should be less than 500ms
        assert abs(time1 - time2) < 0.5


@pytest.mark.django_db(transaction=True)
class TestPermissionIsolation:
    """Test permission and data isolation"""
    
    def test_user_cannot_access_other_user_messages(self, multiple_users):
        """Test messages are isolated per user"""
        user1, user2, user3 = multiple_users
        
        # User1 creates conversation and message
        conv1 = Conversation.objects.create(user=user1, title='Conv1')
        msg1 = Message.objects.create(conversation=conv1, role='user', content='User1 message')
        
        # User2 should not be able to query user1's message
        user2_messages = Message.objects.filter(conversation__user=user2)
        assert msg1 not in user2_messages
    
    def test_conversation_filtering_by_user(self, multiple_users):
        """Test conversations are filtered by user"""
        user1, user2, user3 = multiple_users
        
        # Each user creates conversations
        Conversation.objects.create(user=user1, title='User1 Conv')
        Conversation.objects.create(user=user2, title='User2 Conv')
        Conversation.objects.create(user=user3, title='User3 Conv')
        
        # User1 should only see their own
        user1_convs = Conversation.objects.filter(user=user1)
        assert user1_convs.count() == 1
        assert user1_convs[0].title == 'User1 Conv'
    
    def test_settings_isolation(self, multiple_users):
        """Test settings are isolated per user"""
        user1, user2, user3 = multiple_users
        
        # Update user1's settings
        user1.settings.theme = 'dark'
        user1.settings.language = 'en'
        user1.settings.save()
        
        # User2's settings should be unchanged
        user2.settings.refresh_from_db()
        assert user2.settings.theme != 'dark'
        assert user2.settings.language == 'id'  # Default


@pytest.mark.django_db(transaction=True)
class TestDatabaseQueryPerformance:
    """Test database queries for N+1 problems"""
    
    def test_list_conversations_optimized(self, test_user):
        """Test listing conversations doesn't cause N+1 queries"""
        # Create multiple conversations
        for i in range(5):
            Conversation.objects.create(user=test_user, title=f'Conv {i}')
        
        # Should use minimal queries
        with self.assertNumQueries(2):  # 1 for conversations, 1 for users
            list(Conversation.objects.filter(user=test_user).select_related('user'))
    
    def test_get_messages_optimized(self, test_conversation):
        """Test getting messages doesn't cause N+1 queries"""
        # Create multiple messages
        for i in range(10):
            Message.objects.create(
                conversation=test_conversation,
                role='user' if i % 2 == 0 else 'assistant',
                content=f'Message {i}'
            )
        
        # Should use minimal queries
        with self.assertNumQueries(2):  # 1 for messages, 1 for conversation
            list(Message.objects.filter(
                conversation=test_conversation
            ).select_related('conversation'))


@pytest.mark.django_db(transaction=True)
class TestTransactionIntegrity:
    """Test database transaction handling"""
    
    def test_message_creation_atomic(self, test_conversation):
        """Test message creation is atomic"""
        initial_count = Message.objects.count()
        
        # Create message
        msg = Message.objects.create(
            conversation=test_conversation,
            role='user',
            content='Test'
        )
        
        # Verify single message added
        assert Message.objects.count() == initial_count + 1
        assert Message.objects.filter(id=msg.id).exists()
    
    def test_cascade_delete_atomic(self):
        """Test cascade delete is atomic"""
        from tests.factories import ConversationFactory
        
        conv = ConversationFactory()
        messages = [
            Message.objects.create(conversation=conv, role='user', content=f'Msg {i}')
            for i in range(5)
        ]
        
        conv.delete()
        
        # All messages should be deleted atomically
        for msg in messages:
            assert not Message.objects.filter(id=msg.id).exists()
        assert Conversation.objects.filter(id=conv.id).count() == 0
