import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import escalation_guide
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Query yang akan match "WiFi Access" (yang punya invalid link)
query_wifi = "wifi tamu tidak bisa konek, tolong bantu"

print("=" * 70)
print("TEST 1: Query dengan WiFi (form has INVALID link)")
print("=" * 70)
print("Query: " + query_wifi)
print()

response = escalation_guide(query_wifi, vector_store, embedding_service)
print("Response:")
print(response)
print()

# Query yang akan match Acces Control Device (valid link)
query_acces = "akses pintu masuk error"

print("=" * 70)
print("TEST 2: Query dengan Access Control (form has VALID link)")
print("=" * 70)
print("Query: " + query_acces)
print()

response = escalation_guide(query_acces, vector_store, embedding_service)
print("Response:")
print(response)
