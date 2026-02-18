from django.contrib import admin
from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'category', 'created_at', 'is_active']
    list_filter = ['category', 'created_at', 'is_active']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'chunk_index', 'created_at']
    list_filter = ['document', 'created_at']
    search_fields = ['content']
    readonly_fields = ['created_at']
