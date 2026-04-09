"""
Signal handlers for user-related model events
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import UserProfile, UserSettings


@receiver(post_save, sender=User)
def create_user_profile_and_settings(sender, instance, created, **kwargs):
    """
    Automatically create UserProfile and UserSettings when a new User is created
    """
    if created:
        # Create user profile
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'company': 'Pertamina'}
        )
        
        # Create user settings with defaults
        UserSettings.objects.get_or_create(
            user=instance,
            defaults={
                'theme': 'auto',
                'language': 'id',
                'chatbot_response_timeout': 30,
                'enable_notifications': True,
                'enable_history_logging': True,
                'is_profile_public': False,
                'receive_email_updates': False,
            }
        )


@receiver(post_save, sender=User)
def save_user_profiles(sender, instance, **kwargs):
    """
    Save user profile when user is saved
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
    
    if hasattr(instance, 'settings'):
        instance.settings.save()
