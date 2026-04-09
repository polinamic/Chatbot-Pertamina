"""
Unit tests for models
Tests business logic at the model level
"""
import pytest
from django.contrib.auth.models import User
from apps.users.models import UserProfile, UserSettings
from apps.chatbot.models import Conversation, Message
from tests.factories import UserFactory, UserProfileFactory, UserSettingsFactory


@pytest.mark.django_db(transaction=True)
class TestUserModel:
    """Test User model"""
    
    def test_user_creation(self):
        """Test creating a new user"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123'
        )
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.is_active is True
        assert user.check_password('TestPassword123')
    
    def test_user_password_hashing(self):
        """Test that passwords are hashed"""
        user = User.objects.create_user(
            username='testuser',
            password='TestPassword123'
        )
        assert user.password != 'TestPassword123'
        assert user.check_password('TestPassword123')
        assert not user.check_password('WrongPassword')
    
    def test_duplicate_username_raises_error(self):
        """Test that duplicate usernames raise error"""
        User.objects.create_user(username='testuser', password='pass')
        with pytest.raises(Exception):  # IntegrityError
            User.objects.create_user(username='testuser', password='pass')
    
    def test_user_string_representation(self):
        """Test __str__ method"""
        user = UserFactory(username='john')
        assert str(user) == 'john'


@pytest.mark.django_db(transaction=True)
class TestUserProfileModel:
    """Test UserProfile model"""
    
    def test_profile_creation(self, test_user):
        """Test that profile is auto-created via signals"""
        # Profile is auto-created by signal, so check it exists
        assert hasattr(test_user, 'profile')
        profile = test_user.profile
        assert profile.user == test_user
        assert profile.company == 'Pertamina'  # Default from signal
        
        # Test updating profile
        profile.role = 'U'
        profile.phone = '08123456789'
        profile.save()
        
        profile.refresh_from_db()
        assert profile.role == 'U'
        assert profile.phone == '08123456789'
    
    def test_profile_auto_created_on_signup(self, test_user_with_profile_and_settings):
        """Test that profile is auto-created via signals"""
        user = test_user_with_profile_and_settings
        assert hasattr(user, 'profile')
        assert user.profile.company == 'Pertamina'
    
    def test_profile_role_choices(self, test_user):
        """Test that profile role can be set to valid choice"""
        profile = test_user.profile
        valid_roles = ['U', 'A', 'M']  # User, Admin, Manager
        for role in valid_roles:
            profile.role = role
            profile.save()
            profile.refresh_from_db()
            assert profile.role == role
    
    def test_profile_has_onetoone_with_user(self, test_user):
        """Test OneToOne relationship - only one profile per user"""
        # Profile is auto-created by signal
        profile = test_user.profile
        assert profile is not None
        assert UserProfile.objects.filter(user=test_user).count() == 1
        
        # Trying to create another should fail
        from django.db.utils import IntegrityError
        import pytest
        with pytest.raises(IntegrityError):
            UserProfile.objects.create(user=test_user, role='A')


@pytest.mark.django_db(transaction=True)
class TestUserSettingsModel:
    """Test UserSettings model"""
    
    def test_settings_creation(self, test_user):
        """Test that settings are auto-created and can be modified"""
        # Settings are auto-created by signal
        settings = test_user.settings
        assert settings is not None
        assert settings.user == test_user
        assert settings.theme == 'auto'  # Default from signal
        assert settings.language == 'id'  # Default from signal
        
        # Test updating settings
        settings.theme = 'dark'
        settings.language = 'en'
        settings.enable_notifications = False
        settings.save()
        
        settings.refresh_from_db()
        assert settings.theme == 'dark'
        assert settings.language == 'en'
        assert settings.enable_notifications is False
    
    def test_settings_auto_created_on_signup(self, test_user_with_profile_and_settings):
        """Test that settings are auto-created via signals"""
        user = test_user_with_profile_and_settings
        assert hasattr(user, 'settings')
        assert user.settings.theme in ['light', 'dark', 'auto']
    
    def test_settings_user_isolation(self, multiple_users):
        """Test that each user has separate settings"""
        user1, user2, user3 = multiple_users
        
        # Get original theme for user2 (user1 in the fixture = index 1 = dark)
        original_user2_theme = user2.settings.theme
        
        # Change settings for user1
        user1.settings.theme = 'dark'
        user1.settings.save()
        
        # User2 should keep their original theme
        user2.settings.refresh_from_db()
        
        assert user1.settings.theme == 'dark'
        assert user2.settings.theme == original_user2_theme
    
    def test_settings_defaults(self, test_user):
        """Test default settings values when auto-created"""
        # Settings are auto-created by signal when user is created
        settings = test_user.settings
        assert settings.theme == 'auto'
        assert settings.language == 'id'
        assert settings.chatbot_response_timeout == 30
        assert settings.enable_notifications is True
        assert settings.enable_history_logging is True
        assert settings.enable_notifications is True


@pytest.mark.django_db(transaction=True)
class TestConversationModel:
    """Test Conversation model"""
    
    def test_conversation_creation(self, test_user):
        """Test creating a conversation"""
        conversation = Conversation.objects.create(
            user=test_user,
            title='Test Conversation'
        )
        assert conversation.user == test_user
        assert conversation.title == 'Test Conversation'
        assert conversation.is_archived is False
    
    def test_conversation_user_relationship(self, test_user):
        """Test ForeignKey relationship with User"""
        conv = Conversation.objects.create(user=test_user, title='Test')
        assert conv.user.username == 'testuser'
    
    def test_conversation_ordering(self, test_user):
        """Test conversations ordered by created_at (descending)"""
        conv1 = Conversation.objects.create(user=test_user, title='First')
        conv2 = Conversation.objects.create(user=test_user, title='Second')
        
        conversations = list(Conversation.objects.filter(user=test_user))
        assert conversations[0].title == 'Second'
        assert conversations[1].title == 'First'
    
    def test_user_has_many_conversations(self, test_user):
        """Test one user can have many conversations"""
        for i in range(5):
            Conversation.objects.create(user=test_user, title=f'Conv {i}')
        
        assert test_user.conversations.count() == 5


@pytest.mark.django_db(transaction=True)
class TestMessageModel:
    """Test Message model"""
    
    def test_message_creation(self, test_conversation):
        """Test creating a message"""
        message = Message.objects.create(
            conversation=test_conversation,
            role='user',
            content='Test message'
        )
        assert message.conversation == test_conversation
        assert message.role == 'user'
        assert message.content == 'Test message'
    
    def test_message_roles(self, test_conversation):
        """Test message role choices"""
        user_msg = Message.objects.create(
            conversation=test_conversation,
            role='user',
            content='User message'
        )
        assistant_msg = Message.objects.create(
            conversation=test_conversation,
            role='assistant',
            content='Assistant response'
        )
        assert user_msg.role == 'user'
        assert assistant_msg.role == 'assistant'
    
    def test_conversation_has_many_messages(self, test_conversation):
        """Test conversation can have many messages"""
        for i in range(10):
            Message.objects.create(
                conversation=test_conversation,
                role='user' if i % 2 == 0 else 'assistant',
                content=f'Message {i}'
            )
        
        assert test_conversation.messages.count() == 10
    
    def test_message_ordering(self, test_conversation):
        """Test messages ordered by created_at (ascending)"""
        msg1 = Message.objects.create(conversation=test_conversation, role='user', content='First')
        msg2 = Message.objects.create(conversation=test_conversation, role='assistant', content='Second')
        
        messages = list(test_conversation.messages.all())
        assert messages[0].content == 'First'
        assert messages[1].content == 'Second'
    
    def test_message_deletion_cascade(self):
        """Test messages deleted when conversation deleted"""
        from tests.factories import ConversationFactory
        conv = ConversationFactory()
        Message.objects.create(conversation=conv, role='user', content='Test')
        
        assert Message.objects.count() == 1
        conv.delete()
        assert Message.objects.count() == 0


@pytest.mark.django_db(transaction=True)
class TestDataIntegrity:
    """Test data integrity and relationships"""
    
    def test_user_profile_settings_relationships(self, test_user_with_profile_and_settings):
        """Test User -> Profile -> Settings chain works"""
        user = test_user_with_profile_and_settings
        
        # Can access via user
        assert user.profile.company == 'Pertamina'
        assert user.settings.language == 'id'
        
        # Update settings
        user.settings.language = 'en'
        user.settings.save()
        
        # Verify update
        user.refresh_from_db()
        assert user.settings.language == 'en'
    
    def test_user_conversations_messages(self, test_user):
        """Test User -> Conversation -> Message chain"""
        # Create conversation
        conv = Conversation.objects.create(user=test_user, title='Test')
        
        # Create messages
        msg1 = Message.objects.create(conversation=conv, role='user', content='Hi')
        msg2 = Message.objects.create(conversation=conv, role='assistant', content='Hello')
        
        # Access via user
        assert test_user.conversations.count() == 1
        assert test_user.conversations.first().messages.count() == 2
