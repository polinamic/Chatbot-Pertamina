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
