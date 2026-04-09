import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.chat_service import escalation_guide
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Test the exact query from logs
query = "Mas/Mbak, akses pintu masuk ruangan saya error nih kartu ID-"

print(f"Query: {query}")
print()

response = escalation_guide(query, vector_store, embedding_service)

print("Response:")
print(response[:500] + "..." if len(response) > 500 else response)
