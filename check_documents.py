import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Document as DashboardDocument
from apps.rag.models import Document as RAGDocument, DocumentChunk

print("=" * 60)
print("UPLOADED DOCUMENT CHECK")
print("=" * 60)

# Check dashboard documents
dashboard_docs = DashboardDocument.objects.all().order_by('-id')
print(f"\nDashboard Documents ({DashboardDocument.objects.count()} total):")
for doc in dashboard_docs[:5]:
    print(f"  ID {doc.id}: {doc.file_name} (size={doc.file_size}, processed={doc.is_processed})")

# Check RAG documents
rag_docs = RAGDocument.objects.all().order_by('-id')
print(f"\nRAG Documents ({RAGDocument.objects.count()} total):")
for doc in rag_docs[:5]:
    print(f"  ID {doc.id}: {doc.title} (chunks={doc.chunks.count()})")

# Check chunks
chunks = DocumentChunk.objects.all().order_by('-id')
print(f"\nDocument Chunks ({DocumentChunk.objects.count()} total):")
for chunk in chunks[:5]:
    print(f"  ID {chunk.id}: Doc {chunk.document.id}, Index {chunk.chunk_index}, Size {len(chunk.content)}")

print("\n" + "=" * 60)
