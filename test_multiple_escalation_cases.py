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

# Test multiple scenarios
test_cases = [
    ("bertu buatlah tiketnya, bagi link untuk membuat tiketnya aja", "Generic 'ticket' request"),
    ("bagaimana cara membuat tiket untuk akses pintu", "Access control ticket request"),
    ("wifi tidak bisa, tolong buat tiket", "WiFi + ticket request"),
    ("gimana cara membuat form untuk sap error", "Form request with context"),
]

print("=" * 80)
print("TESTING ESCALATION FLOW - INTENT + RESPONSE")
print("=" * 80)

for query, description in test_cases:
    print()
    print("Query: " + query)
    print("Description: " + description)
    
    # Detect intent
    intent = detect_intent(query, embedding_service)
    print("Intent: " + str(intent))
    
    if intent in ["REQUEST_IT_SUPPORT", "ESCALATION"]:
        # Get escalation guide
        guide = escalation_guide(query, vector_store, embedding_service)
        
        # Show response
        response_lines = guide.split('\n')
        print("\nResponse:")
        for line in response_lines[:10]:  # Show first 10 lines
            print("  " + line)
        
        # Check length
        if len(guide) > 300:
            print("  WARNING: Response too long!")
    else:
        print("(No escalation guide for this intent)")
    
    print("-" * 80)

print()
print("=" * 80)
