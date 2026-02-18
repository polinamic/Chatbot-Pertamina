from django.db import models


class Document(models.Model):
    """Model untuk menyimpan dokumen yang akan digunakan dalam RAG"""
    title = models.CharField(max_length=255)
    content = models.TextField()
    file = models.FileField(upload_to='documents/')
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """Model untuk menyimpan chunk dari dokumen yang sudah diproses"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding_id = models.CharField(max_length=255, null=True, blank=True)  # Pinecone ID
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        verbose_name = 'Document Chunk'
        verbose_name_plural = 'Document Chunks'
        unique_together = ['document', 'chunk_index']

    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_index}"
