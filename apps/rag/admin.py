from django.contrib import admin
from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'category', 'is_active', 'created_at']
    search_fields = ['title', 'category']
    list_filter = ['category', 'is_active']
    ordering = ['-created_at']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'chunk_index', 'created_at']
    search_fields = ['document__title']
    ordering = ['document', 'chunk_index']