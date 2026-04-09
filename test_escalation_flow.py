import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import detect_intent, escalation_guide
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Simulate user query dari screenshot: "bertu buatlah tiketnya, bagi link untuk membuat tiketnya aja"
query = "bertu buatlah tiketnya, bagi link untuk membuat tiketnya aja"

print("Query: " + query)
print()

# Step 1: Check intent detection
intent = detect_intent(query, embedding_service)
print("1. Intent detected: " + str(intent))
print()

# Step 2: If REQUEST_IT_SUPPORT, call escalation_guide
if intent in ["REQUEST_IT_SUPPORT", "ESCALATION"]:
    print("2. Calling escalation_guide()...")
    guide = escalation_guide(query, vector_store, embedding_service)
    print()
    print("Response from escalation_guide():")
    print("=" * 70)
    print(guide)
    print("=" * 70)
    print()
    
    # Check length
    length = len(guide)
    if length > 500:
        print("WARNING: Response too long ({} chars)".format(length))
        print("Should be max 200 chars for just form + link")
    else:
        print("OK: Response length reasonable ({} chars)".format(length))
