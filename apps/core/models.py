from django.db import models
import uuid


class LLMConfig(models.Model):
    """Configuration for LLM providers"""
    llm_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    provider_name = models.CharField(max_length=128, default='', blank=True)
    model_name = models.CharField(max_length=128, default='', blank=True)
    temperature = models.DecimalField(max_digits=3, decimal_places=2, default=0.7)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'llm_config'
        verbose_name = 'LLM Configuration'
        verbose_name_plural = 'LLM Configurations'

    def __str__(self):
        return f"{self.provider_name} - {self.model_name}"


class Conversation(models.Model):
    """Conversation between user and chatbot"""
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('ESCALATED', 'Escalated'),
        ('ARCHIVED', 'Archived'),
    ]
    
    conversation_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    user_id = models.CharField(max_length=10, default='', blank=True)
    llm_id = models.CharField(max_length=10, default='', blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'conversation'
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Conversation {self.conversation_id}"


class Message(models.Model):
    """Messages in a conversation"""
    SENDER_CHOICES = [
        ('USER', 'User'),
        ('BOT', 'Bot'),
    ]
    
    message_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    conversation_id = models.CharField(max_length=10, default='', blank=True)
    sender_type = models.CharField(max_length=20, choices=SENDER_CHOICES, default='USER')
    content = models.TextField(default='', blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = 'message'
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        indexes = [
            models.Index(fields=['conversation_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Message {self.message_id}"


class Document(models.Model):
    """Documents for RAG ingestion"""
    document_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    title = models.CharField(max_length=128, default='')
    source = models.CharField(max_length=50, default='', blank=True)
    content = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = 'document'
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['uploaded_at']),
        ]

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """Chunks of documents with embeddings"""
    document_chunk_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    document_id = models.CharField(max_length=10, default='', blank=True)
    chunk_text = models.TextField(default='', blank=True)
    embedding_vector = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = 'document_chunk'
        verbose_name = 'Document Chunk'
        verbose_name_plural = 'Document Chunks'
        indexes = [
            models.Index(fields=['document_id']),
        ]

    def __str__(self):
        return f"Chunk {self.document_chunk_id}"


class RetrievalLog(models.Model):
    """Logs for document retrieval during conversation"""
    retrieval_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    message_id = models.CharField(max_length=10, default='', blank=True)
    document_chunk_id = models.CharField(max_length=10, default='', blank=True)
    similarity_score = models.DecimalField(max_digits=6, decimal_places=5, default=0)
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = 'retrieval_log'
        verbose_name = 'Retrieval Log'
        verbose_name_plural = 'Retrieval Logs'
        indexes = [
            models.Index(fields=['message_id']),
            models.Index(fields=['document_chunk_id']),
        ]

    def __str__(self):
        return f"Retrieval {self.retrieval_id}"


class EscalationLog(models.Model):
    """Logs for escalated conversations"""
    escalation_id = models.CharField(
        max_length=10, 
        primary_key=True, 
        default='',
        editable=False
    )
    message_id = models.CharField(max_length=10, default='', blank=True)
    reason = models.TextField(default='', blank=True)
    fallback_message = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = 'escalation_log'
        verbose_name = 'Escalation Log'
        verbose_name_plural = 'Escalation Logs'
        indexes = [
            models.Index(fields=['message_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Escalation {self.escalation_id}"


class ActivityLog(models.Model):
    """Model untuk mencatat aktivitas user"""
    ACTION_CHOICES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('SEARCH', 'Search'),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='VIEW')
    description = models.TextField(default='', blank=True)
    user_id = models.CharField(max_length=10, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

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
