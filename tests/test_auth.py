"""
Authentication & Authorization tests
Tests login, signup, access control, and user isolation
"""
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from apps.users.models import UserProfile, UserSettings


@pytest.mark.django_db(transaction=True)
class TestSignupFlow:
    """Test signup functionality"""
    
    def test_signup_page_loads(self, client):
        """Test signup page is accessible"""
        response = client.get('/auth/signup/')
        assert response.status_code == 200
        assert 'signup' in response.content.decode().lower()
    
    def test_successful_signup(self, client, valid_signup_data):
        """Test successful user signup"""
        response = client.post('/auth/signup/', valid_signup_data)
        
        # User should be created
        assert User.objects.filter(username='newuser123').exists()
        user = User.objects.get(username='newuser123')
        
        # Profile and settings should be auto-created
        assert hasattr(user, 'profile')
        assert hasattr(user, 'settings')
    
    def test_signup_not_auto_login(self, client, valid_signup_data):
        """Test that signup does NOT auto-login user"""
        response = client.post('/auth/signup/', valid_signup_data)
        
        # User should not be authenticated after signup
        assert not response.wsgi_request.user.is_authenticated
        
        # Should show success message
        assert 'success' in response.content.decode().lower() or 'login' in response.content.decode().lower()
    
    def test_signup_redirect_to_login(self, client, valid_signup_data):
        """Test that signup shows redirect to login"""
        response = client.post('/auth/signup/', valid_signup_data)
        
        # Response should contain login link
        content = response.content.decode().lower()
        assert 'login' in content or 'masuk' in content
    
    def test_signup_duplicate_username(self, client, test_user, valid_signup_data):
        """Test signup fails with duplicate username"""
        valid_signup_data['username'] = 'testuser'  # Already exists
        response = client.post('/auth/signup/', valid_signup_data)
        
        # Should show error
        assert 'error' in response.content.decode().lower() or 'sudah' in response.content.decode().lower()
    
    def test_signup_invalid_password(self, client):
        """Test signup fails with weak password"""
        weak_password_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'weak'  # Too short, no uppercase, no digit
        }
        response = client.post('/auth/signup/', weak_password_data)
        
        # User should NOT be created
        assert not User.objects.filter(username='newuser').exists()
        assert 'error' in response.content.decode().lower()
    
    def test_signup_missing_required_fields(self, client):
        """Test signup fails with missing fields"""
        incomplete_data = {
            'username': 'testuser',
            # missing email and password
        }
        response = client.post('/auth/signup/', incomplete_data)
        
        assert 'error' in response.content.decode().lower()


@pytest.mark.django_db(transaction=True)
class TestLoginFlow:
    """Test login functionality"""
    
    def test_login_page_loads(self, client):
        """Test login page is accessible"""
        response = client.get('/auth/login/')
        assert response.status_code == 200
    
    def test_successful_login(self, client, test_user, valid_login_data):
        """Test successful login"""
        response = client.post('/auth/login/', valid_login_data, follow=True)
        
        # User should be authenticated
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user.username == 'testuser'
    
    def test_login_wrong_password(self, client, test_user):
        """Test login fails with wrong password"""
        response = client.post('/auth/login/', {
            'username': 'testuser',
            'password': 'WrongPassword123'
        })
        
        # User should NOT be authenticated
        assert not response.wsgi_request.user.is_authenticated
        assert 'error' in response.content.decode().lower() or 'salah' in response.content.decode().lower()
    
    def test_login_nonexistent_user(self, client, invalid_login_data):
        """Test login fails with nonexistent user"""
        response = client.post('/auth/login/', invalid_login_data)
        
        assert not response.wsgi_request.user.is_authenticated
    
    def test_login_updates_last_login(self, client, test_user):
        """Test that login updates last_login timestamp"""
        old_last_login = test_user.last_login
        
        client.post('/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123'
        })
        
        test_user.refresh_from_db()
        assert test_user.last_login > old_last_login
    
    def test_login_creates_session(self, client, test_user):
        """Test that login creates session"""
        response = client.post('/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123'
        }, follow=True)
        
        assert 'sessionid' in client.cookies


@pytest.mark.django_db(transaction=True)
class TestAccessControl:
    """Test authentication-required pages"""
    
    def test_unauthenticated_cannot_access_chat(self, client):
        """Test unauthenticated user cannot access chat page"""
        response = client.get('/chatbot/', follow=True)
        
        # Should redirect to login
        assert response.status_code == 200
        assert 'login' in response.request['PATH_INFO'].lower()
    
    def test_authenticated_can_access_chat(self, authenticated_client):
        """Test authenticated user can access chat page"""
        response = authenticated_client.get('/chatbot/')
        
        # Should load chat page (not redirect)
        assert response.status_code == 200 or 'chat' in response.content.decode().lower()
    
    def test_unauthenticated_cannot_access_profile(self, client):
        """Test unauthenticated user cannot access profile"""
        response = client.get('/auth/profile/', follow=True)
        
        # Should redirect to login
        assert 'login' in response.request['PATH_INFO'].lower()
    
    def test_authenticated_can_access_profile(self, authenticated_client):
        """Test authenticated user can access their profile"""
        response = authenticated_client.get('/auth/profile/')
        
        assert response.status_code == 200
    
    def test_unauthenticated_cannot_access_settings(self, client):
        """Test unauthenticated user cannot access settings"""
        response = client.get('/auth/settings/', follow=True)
        
        # Should redirect to login
        assert 'login' in response.request['PATH_INFO'].lower()
    
    def test_authenticated_can_access_settings(self, authenticated_client):
        """Test authenticated user can access settings"""
        response = authenticated_client.get('/auth/settings/')
        
        assert response.status_code == 200


@pytest.mark.django_db(transaction=True)
class TestDataIsolation:
    """Test user data isolation"""
    
    def test_users_cannot_see_each_other_settings(self, multiple_users):
        """Test users cannot access or modify other users' settings"""
        user1, user2, user3 = multiple_users
        
        # User1 settings are separate
        user1.settings.theme = 'dark'
        user1.settings.save()
        
        # User2 settings should NOT change
        user2.settings.refresh_from_db()
        assert user2.settings.theme == 'light'
    
    def test_users_cannot_see_each_other_conversations(self, multiple_users):
        """Test users cannot see other users' conversations"""
        from apps.chatbot.models import Conversation
        
        user1, user2, user3 = multiple_users
        
        # User1 creates conversation
        conv1 = Conversation.objects.create(user=user1, title='User1 Conv')
        
        # User2 should not see it
        assert conv1 not in user2.conversations.all()
        assert user1.conversations.count() == 1
        assert user2.conversations.count() == 0
    
    def test_users_cannot_see_each_other_messages(self, multiple_users):
        """Test users cannot see other users' messages"""
        from apps.chatbot.models import Conversation, Message
        
        user1, user2, user3 = multiple_users
        
        # User1 creates conversation with message
        conv1 = Conversation.objects.create(user=user1, title='Conv')
        msg1 = Message.objects.create(conversation=conv1, role='user', content='User1 message')
        
        # User2 cannot see message
        assert msg1 not in Message.objects.filter(conversation__user=user2)
    
    def test_profile_isolation(self, multiple_users):
        """Test user profiles are isolated"""
        user1, user2, user3 = multiple_users
        
        # Update user1 profile
        user1.profile.phone = '08111111111'
        user1.profile.save()
        
        # User2 profile should not change
        user2.profile.refresh_from_db()
        assert user2.profile.phone != '08111111111'


@pytest.mark.django_db(transaction=True)
class TestLogout:
    """Test logout functionality"""
    
    def test_logout_redirects_to_login(self, authenticated_client):
        """Test logout redirects to login page"""
        response = authenticated_client.get('/auth/logout/', follow=True)
        
        # Should redirect to login
        assert 'login' in response.request['PATH_INFO'].lower()
    
    def test_logout_clears_session(self, authenticated_client):
        """Test logout clears user session"""
        authenticated_client.get('/auth/logout/')
        
        # Make another request
        response = authenticated_client.get('/chatbot/', follow=True)
        
        # Should redirect to login (no longer authenticated)
        assert 'login' in response.request['PATH_INFO'].lower()


@pytest.mark.django_db(transaction=True)
class TestSessionSecurity:
    """Test session security"""
    
    def test_session_cookie_exists(self, authenticated_client):
        """Test session cookie is created"""
        authenticated_client.get('/chatbot/')
        
        assert 'sessionid' in authenticated_client.cookies
    
    def test_inactive_user_cannot_login(self, client):
        """Test inactive users cannot login"""
        user = User.objects.create_user(
            username='inactive',
            password='Pass123'
        )
        user.is_active = False
        user.save()
        
        response = client.post('/auth/login/', {
            'username': 'inactive',
            'password': 'Pass123'
        })
        
        assert not response.wsgi_request.user.is_authenticated
