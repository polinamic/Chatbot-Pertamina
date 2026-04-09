import os, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import _find_escalation_by_keywords
from apps.rag.models import DocumentChunk

query = "akses pintu masuk ruangan saya error nih"

print(f"Query: {query}\n")

# Test keyword matching
keyword_result = _find_escalation_by_keywords(query)

if keyword_result:
    # Extract form name from result
    for line in keyword_result.split('\n'):
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
            print(f"✓ Keyword matching returned form: {form_name}")
            break
else:
    print("✗ Keyword matching: No results")
