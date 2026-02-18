from rest_framework import serializers
from .models import Document, DocumentChunk


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ['id', 'chunk_index', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class DocumentSerializer(serializers.ModelSerializer):
    chunks = DocumentChunkSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'title', 'content', 'file', 'category', 'created_at', 'updated_at', 'is_active', 'chunks']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DocumentListSerializer(serializers.ModelSerializer):
    chunks_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['id', 'title', 'category', 'created_at', 'is_active', 'chunks_count']
        read_only_fields = ['id', 'created_at']

    def get_chunks_count(self, obj):
        return obj.chunks.count()
