import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import _find_escalation_by_keywords
from apps.rag.models import DocumentChunk

query = "wifi tamu tidak bisa konek"

print("Query: " + query)
print()

# Try keyword matching
result = _find_escalation_by_keywords(query)

if result:
    # Extract form name
    for line in result.split('\n'):
        if 'NAMA FORM:' in line:
            form = line.split('NAMA FORM:')[1].strip()
            print("Keyword match returned: " + form)
            
            # Check if this form has invalid link
            for line2 in result.split('\n'):
                if 'Link:' in line2:
                    link = line2.split('Link:')[1].strip()
                    print("Link: " + link)
                    
                    if '[link_belum_tersedia' in link.lower():
                        print(">>> This link is INVALID (placeholder)")
                    else:
                        print(">>> This link is VALID")
            break
else:
    print("No keyword match found")
