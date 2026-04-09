import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.retrieval import retrieve_context
from apps.rag.models import DocumentChunk
import logging
import traceback

# Enable logging to see errors
logging.basicConfig(level=logging.DEBUG)

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Test query
query = 'kartu akses tidak bisa membuka pintu'

# Retrieve ESCALATION context
try:
    results = retrieve_context(query, vector_store, embedding_service, doc_type='ESCALATION', top_k=3)
    print(f'Found {len(results)} results for ESCALATION:')
except Exception as e:
    print(f'ERROR during retrieval: {e}')
    import traceback
    traceback.print_exc()
    results = []

print(f'Found {len(results)} results for ESCALATION:')
for i, r in enumerate(results):
    score = r.get('score')
    content = r.get('content')
    print(f'{i+1}. Score: {score:.4f}')
    print(f'   Content: {content[:150]}...')
    print()

# Also check what chunks exist
print("\n=== Checking database ===")
chunks = DocumentChunk.objects.select_related('document').filter(document__doc_type='ESCALATION')[:5]
print(f"Sample ESCALATION chunks in DB:")
for chunk in chunks:
    print(f"- {chunk.document.title}: {chunk.content[:100]}...")
