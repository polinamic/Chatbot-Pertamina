import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.retrieval import retrieve_context

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Test different queries
queries = [
    'kartu akses tidak bisa membuka pintu',
    'acces control device',
    'pembuat tiket untuk access control',
    'form kartu akses',
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    results = retrieve_context(query, vector_store, embedding_service, doc_type='ESCALATION', top_k=3)
    
    if results:
        for i, r in enumerate(results):
            print(f"\n{i+1}. {r.get('content').split(chr(10))[0]} (score: {r.get('score'):.4f})")
    else:
        print("No results found")
