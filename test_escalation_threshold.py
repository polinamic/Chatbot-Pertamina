import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.retrieval import retrieve_context

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Test various access-related queries
queries = [
    "Mas/Mbak, akses pintu masuk ruangan saya error nih kartu ID-",
    "akses pintu",
    "kartu akses",
    "access control",
    "acces control device",
]

print("Checking reranker scores for ESCALATION queries:\n")

for query in queries:
    results = retrieve_context(query, vector_store, embedding_service, doc_type='ESCALATION', top_k=1)
    
    if results:
        score = results[0].get('score')
        content = results[0].get('content')
        form = content.split('\n')[0] if content else "N/A"
        print(f"Query: '{query}'")
        print(f"  Top result: {form}")
        print(f"  Score: {score:.4f}")
        print(f"  Passes 0.35? {'YES' if score >= 0.35 else 'NO'}")
        print(f"  Passes 0.01? {'YES' if score >= 0.01 else 'NO'}")
        print()
