"""
Factory-boy factories for test data generation
Simplifies creating test data with realistic values
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.contrib.auth.models import User
from apps.users.models import UserProfile, UserSettings
from apps.chatbot.models import Conversation, Message

fake = Faker()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if create:
            obj.set_password(extracted or 'TestPassword123')
            obj.save()


class UserProfileFactory(DjangoModelFactory):
    """Factory for creating user profiles"""
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    role = 'U'  # Regular user
    department = 'IT'
    company = 'Pertamina'
    phone = factory.Faker('phone_number')
    bio = factory.Faker('text', max_nb_chars=100)
    is_verified = False


class UserSettingsFactory(DjangoModelFactory):
    """Factory for creating user settings"""
    class Meta:
        model = UserSettings

    user = factory.SubFactory(UserFactory)
    theme = 'light'
    language = 'id'
    chatbot_response_timeout = 30
    enable_notifications = True
    enable_history_logging = True
    is_profile_public = False
    receive_email_updates = False


class ConversationFactory(DjangoModelFactory):
    """Factory for creating conversations"""
    class Meta:
        model = Conversation

    user = factory.SubFactory(UserFactory)
    title = factory.Faker('sentence')
    is_archived = False


class MessageFactory(DjangoModelFactory):
    """Factory for creating messages"""
    class Meta:
        model = Message

    conversation = factory.SubFactory(ConversationFactory)
    role = 'user'
    content = factory.Faker('text')
    sources = '[]'
