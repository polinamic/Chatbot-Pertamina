from django.db import models
from django.contrib.auth.models import User
import json


class Conversation(models.Model):
    """Model untuk menyimpan percakapan dengan chatbot"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class Message(models.Model):
    """Model untuk menyimpan pesan dalam percakapan"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='message_set')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.TextField(null=True, blank=True, default='[]')  # Untuk menyimpan RAG sources (JSON as string)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f"{self.conversation.title} - {self.role}"

    def get_sources(self):
        """Helper untuk mengubah JSON string menjadi Python object"""
        try:
            return json.loads(self.sources)
        except:
            return []


# =====================================================
# MODEL BARU UNTUK AGENTIC WORKFLOW
# =====================================================

class ChatSession(models.Model):
    """
    Model untuk menyimpan state percakapan user
    untuk agentic workflow escalation
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_sessions'
    )

    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name='session'
    )

    failure_count = models.IntegerField(
        default=0
    )

    last_problem = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"

    def __str__(self):
        return f"Session {self.conversation.id} - failures:{self.failure_count}"


class UINavigatorMap(models.Model):
    """
    Model pemetaan kategori masalah
    ke langkah UI escalation copilot
    """

    category_name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField()

    ui_steps = models.TextField(
        help_text="Langkah-langkah UI yang harus dilakukan user"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "UI Navigator Map"
        verbose_name_plural = "UI Navigator Maps"

    def __str__(self):
        return self.category_name