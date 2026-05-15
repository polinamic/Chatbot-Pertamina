from django.db import models
from django.contrib.auth.models import User  # Wajib di-import untuk kolom uploaded_by
import uuid

class Document(models.Model):
    # === TAMBAHAN BARU: Pilihan tipe dokumen untuk pemisahan RAG ===
    DOC_TYPES = (
        ('TROUBLESHOOT', 'Langkah Troubleshooting (Solusi Mandiri)'),
        ('ORDER_LINK', 'Link Pemesanan/Pengadaan Item IT Baru'),
        ('INCIDENT_LINK', 'Link Pelaporan Error/Kerusakan'),
    )

    # --- KEBUTUHAN RAG (Struktur Asli Anda) ---
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='documents/', blank=True, null=True)
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES, default='TROUBLESHOOT')

    # --- KEBUTUHAN DASHBOARD UI (Tambahan agar web tidak error) ---
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.IntegerField(null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_processed = models.BooleanField(default=False)  # FIX: Matches migration 0005

    # --- TIMESTAMP ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        # Memprioritaskan file_name untuk tampilan di web admin, jika kosong gunakan title
        return self.file_name if self.file_name else self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks'
    )

    chunk_index = models.IntegerField()
    content = models.TextField()
    
    embedding_vector = models.BinaryField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']