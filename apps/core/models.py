from django.db import models


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
