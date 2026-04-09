import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.basicConfig(level=logging.DEBUG)

from apps.rag.services.chat_service import escalation_guide
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.retrieval import retrieve_context

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Test the exact query from logs
query = "Mas/Mbak, akses pintu masuk ruangan saya error nih kartu ID-"

print(f"=== DIRECT RETRIEVAL TEST ===")
print(f"Query: {query}\n")

# Test retrieval directly
results = retrieve_context(query, vector_store, embedding_service, doc_type='ESCALATION', top_k=1)
print(f"Direct retrieval results: {len(results)}")
if results:
    print(f"  Score: {results[0].get('score')}")
    print(f"  Form: {results[0].get('content').split(chr(10))[0]}")
else:
    print("  No results found!")

print(f"\n=== ESCALATION_GUIDE TEST ===")
response = escalation_guide(query, vector_store, embedding_service)
print(f"Response (first 200 chars):\n{response[:200]}")
