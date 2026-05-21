from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
import secrets
from django.utils import timezone
from datetime import timedelta


class UserProfile(models.Model):
    """Extended user profile"""
    ROLE_CHOICES = [
        ('A', 'Admin'),
        ('U', 'User'),
        ('S', 'Support'),
        ('M', 'Manager'),
    ]
    
    DEPARTMENT_CHOICES = [
        ('IT', 'IT Support'),
        ('HR', 'Human Resources'),
        ('OPS', 'Operations'),
        ('FIN', 'Finance'),
        ('OTHER', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=1, choices=ROLE_CHOICES, default='U')
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, default='OTHER')
    company = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=15, blank=True)
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.user.email})"


class UserSettings(models.Model):
    """
    User-specific settings storage
    Each user has their own settings (not shared globally)
    """
    THEME_CHOICES = [
        ('light', 'Light Mode'),
        ('dark', 'Dark Mode'),
        ('auto', 'Auto (System)'),
    ]

    LANGUAGE_CHOICES = [
        ('id', 'Bahasa Indonesia'),
        ('en', 'English'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    
    # Theme preferences
    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='auto',
        help_text='User preferred theme'
    )
    
    # Language preference
    language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='id',
        help_text='User preferred language'
    )
    
    # Chatbot preferences
    chatbot_response_timeout = models.IntegerField(
        default=30,
        help_text='Timeout in seconds for chatbot responses'
    )
    
    enable_notifications = models.BooleanField(
        default=True,
        help_text='Enable chat notifications'
    )
    
    enable_history_logging = models.BooleanField(
        default=True,
        help_text='Enable saving chat history'
    )
    
    # Privacy settings
    is_profile_public = models.BooleanField(
        default=False,
        help_text='Allow other users to view profile'
    )
    
    # Additional settings
    receive_email_updates = models.BooleanField(
        default=False,
        help_text='Receive email updates and announcements'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Settings'
        verbose_name_plural = 'User Settings'

    def __str__(self):
        return f"Settings for {self.user.username}"


class PasswordResetToken(models.Model):
    """
    Model untuk menyimpan token password reset
    Token di-hash dan disimpan di database untuk keamanan
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_token')
    token_hash = models.CharField(max_length=255, unique=True, help_text='Hashed reset token')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text='Token expiry time')
    is_used = models.BooleanField(default=False, help_text='Whether the token has been used')
    used_at = models.DateTimeField(null=True, blank=True, help_text='When the token was used')

    class Meta:
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['user', 'is_used']),
        ]

    def __str__(self):
        return f"Reset token for {self.user.email}"

    @staticmethod
    def generate_token():
        """
        Generate a cryptographically secure random token
        Returns: plain token (to be sent to user)
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token):
        """
        Hash the token using Django's password hasher
        Returns: hashed token (to be stored in DB)
        """
        return make_password(token)

    def is_valid(self):
        """
        Check if token is still valid (not expired and not used)
        """
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    def create_for_user(cls, user, expiry_minutes=15):
        """
        Create or update password reset token for user
        Invalidates any existing token for this user
        
        Args:
            user: User instance
            expiry_minutes: Token expiry time in minutes
            
        Returns:
            tuple (plain_token, reset_token_obj)
        """
        # Invalidate existing token
        cls.objects.filter(user=user, is_used=False).delete()

        # Generate new token
        plain_token = cls.generate_token()
        token_hash = cls.hash_token(plain_token)

        # Create reset token
        reset_token = cls.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes)
        )

        return plain_token, reset_token

    @classmethod
    def get_user_from_token(cls, token):
        """
        Validate token and return associated user
        
        Args:
            token: Plain token from user
            
        Returns:
            User instance if valid, None otherwise
        """
        # Find all tokens for this token string (since we don't know the hash upfront)
        # We need to check each unused token
        reset_tokens = cls.objects.filter(is_used=False)
        
        for reset_token in reset_tokens:
            if reset_token.is_valid() and check_password(token, reset_token.token_hash):
                return reset_token.user, reset_token

        return None, None

    def mark_as_used(self):
        """Mark token as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
