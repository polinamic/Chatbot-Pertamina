from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password


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
