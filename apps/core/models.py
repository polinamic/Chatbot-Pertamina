from django.db import models
from django.contrib.auth.models import User


class BaseModel(models.Model):
    """Base abstract model with common fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActivityLog(models.Model):
    """Model untuk mencatat aktivitas user"""
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('SEARCH', 'Search'),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    user_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f"{self.action} - {self.created_at}"


class Document(models.Model):
    """Model untuk menyimpan documents yang di-ingest"""
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(null=True, blank=True)  # dalam bytes
    file_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return self.file_name

