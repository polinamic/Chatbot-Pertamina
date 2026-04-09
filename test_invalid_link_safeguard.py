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

# Query untuk test case: Query yang specific untuk WiFi (bukan Access Control)
# WiFi Access has: "wifi, guest, temporer, tamu, jaringan..."
query_wifi = "guest wifi temporer tidak bisa"

print("=" * 70)
print("TEST: Query untuk WiFi GUEST (form has INVALID/placeholder link)")
print("=" * 70)
print("Query: " + query_wifi)
print()

response = escalation_guide(query_wifi, vector_store, embedding_service)
print("Response:")
print(response)
print()

print("=" * 70)
print("EXPECTED BEHAVIOR:")
print("=" * 70)
print("- WiFi Access has INVALID link: [LINK_BELUM_TERSEDIA_DI_CSV]")
print("- Safeguard should reject it")
print("- Should fall back to generic message")
print("- Should NOT return fictional link")
