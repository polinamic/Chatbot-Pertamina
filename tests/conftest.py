"""
pytest configuration and shared fixtures for all tests
"""
import os
import django
import pytest
from faker import Faker

# Set test flag before importing settings
os.environ['TEST_DATABASE'] = 'true'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django
django.setup()

# Now we can import Django stuff
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.test.client import RequestFactory
from apps.users.models import UserProfile, UserSettings
from apps.chatbot.models import Conversation, Message
from rest_framework.test import APIClient

fake = Faker()


# =============================================
# FIXTURES - USER & AUTHENTICATION
# =============================================

@pytest.fixture
def test_user():
    """Create a test user"""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='TestPassword123'
    )
    return user


@pytest.fixture
def test_user_with_profile_and_settings(test_user):
    """Create a test user with profile and settings"""
    profile, _ = UserProfile.objects.get_or_create(
        user=test_user,
        defaults={
            'role': 'U',
            'department': 'IT',
            'company': 'Pertamina',
            'phone': '08123456789'
        }
    )
    settings_obj, _ = UserSettings.objects.get_or_create(
        user=test_user,
        defaults={
            'theme': 'light',
            'language': 'id',
            'enable_notifications': True
        }
    )
    return test_user


@pytest.fixture
def test_admin_user():
    """Create a test admin user"""
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='AdminPassword123'
    )
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'A', 'company': 'Pertamina'}
    )
    return user


@pytest.fixture
def authenticated_client(client, test_user_with_profile_and_settings):
    """Return a client with an authenticated user"""
    client.force_login(test_user_with_profile_and_settings)
    return client


# =============================================
# FIXTURES - CONVERSATIONS & MESSAGES
# =============================================

@pytest.fixture
def test_conversation(test_user):
    """Create a test conversation"""
    conversation = Conversation.objects.create(
        user=test_user,
        title='Test Conversation'
    )
    return conversation


@pytest.fixture
def test_conversation_with_messages(test_conversation):
    """Create a conversation with messages"""
    Message.objects.create(
        conversation=test_conversation,
        role='user',
        content='Test user message'
    )
    Message.objects.create(
        conversation=test_conversation,
        role='assistant',
        content='Test assistant response'
    )
    return test_conversation


# =============================================
# FIXTURES - MULTIPLE USERS (FOR ISOLATION TESTS)
# =============================================

@pytest.fixture
def multiple_users():
    """Create multiple test users for isolation testing"""
    users = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'user{i}',
            email=f'user{i}@example.com',
            password='TestPassword123'
        )
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'company': 'Pertamina'}
        )
        UserSettings.objects.get_or_create(
            user=user,
            defaults={
                'theme': 'light' if i % 2 == 0 else 'dark',
                'language': 'id'
            }
        )
        users.append(user)
    return users


# =============================================
# FIXTURES - FORM DATA
# =============================================

@pytest.fixture
def valid_signup_data():
    """Valid signup form data"""
    return {
        'username': 'newuser123',
        'email': 'newuser@example.com',
        'password': 'NewPassword123'
    }


@pytest.fixture
def valid_login_data(test_user):
    """Valid login form data"""
    return {
        'username': 'testuser',
        'password': 'TestPassword123'
    }


@pytest.fixture
def invalid_login_data():
    """Invalid login form data"""
    return {
        'username': 'nonexistent',
        'password': 'WrongPassword123'
    }


@pytest.fixture
def valid_profile_data():
    """Valid profile update data"""
    return {
        'first_name': 'Test',
        'last_name': 'User',
        'phone': '08123456789',
        'bio': 'Test bio',
        'company': 'Pertamina',
        'department': 'IT'
    }


@pytest.fixture
def valid_settings_data():
    """Valid settings update data"""
    return {
        'theme': 'dark',
        'language': 'en',
        'enable_notifications': False,
        'enable_history_logging': True,
        'receive_email_updates': True,
        'is_profile_public': True,
        'chatbot_response_timeout': 60
    }


# =============================================
# FIXTURES - API REQUEST DATA
# =============================================

@pytest.fixture
def api_signup_payload():
    """API signup payload"""
    return {
        'username': 'apiuser',
        'email': 'apiuser@example.com',
        'password': 'ApiPassword123'
    }


@pytest.fixture
def api_login_payload():
    """API login payload"""
    return {
        'username': 'testuser',
        'password': 'TestPassword123'
    }


@pytest.fixture
def message_payload():
    """Chat message payload"""
    return {
        'content': 'Apa itu Pertamina?'
    }

