import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Suppress logs
import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import escalation_guide, _find_escalation_by_keywords
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

query = "Mas/Mbak, akses pintu masuk ruangan saya error nih kartu ID-"

print(f"Query: {query}\n")

# Test keyword matching first
keyword_result = _find_escalation_by_keywords(query)
if keyword_result:
    print(f"Keyword matching FOUND:\n{keyword_result[:300]}...\n")
else:
    print("Keyword matching: No results\n")

# Test full escalation guide
response = escalation_guide(query, vector_store, embedding_service)
print(f"Escalation Guide Response:\n{response[:500]}...")
