import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.retrieval import retrieve_context

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# The actual query from logs
query = "Mas/Mbak, akses pintu masuk ruangan saya error nih kartu ID-"

print(f"Query: {query}")
print(f"Query length: {len(query)}")
print()

# Try to retrieve ESCALATION docs
results = retrieve_context(query, vector_store, embedding_service, doc_type='ESCALATION', top_k=5)

print(f"Found {len(results)} results:")
for i, r in enumerate(results):
    score = r.get('score')
    content = r.get('content')
    form_name = content.split('\n')[0] if content else "N/A"
    status = "PASS" if score >= 0.35 else "FAIL"
    print(f"{i+1}. Score: {score:.4f} | {status} threshold | {form_name}")
