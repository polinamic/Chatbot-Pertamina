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

query = "Mas/Mbak, akses pintu masuk ruangan saya error nih"

print("Query: " + query + "\n")

# Test escalation guide with new simplified format
try:
    response = escalation_guide(query, vector_store, embedding_service)
    print("Escalation Guide Response:")
    print(response)
except Exception as e:
    print("ERROR: " + str(e))
    import traceback
    traceback.print_exc()
