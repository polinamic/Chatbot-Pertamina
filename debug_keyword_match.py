import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

query = "akses pintu masuk ruangan saya error nih"
keywords = query.lower().split()

print(f"Query: {query}\n")
print("Escalation forms di database:\n")

# Get all ESCALATION chunks
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
)

for chunk in escalation_chunks:
    content = chunk.content.lower()
    lines = content.split('\n')
    
    # Extract name and trigger keywords
    form_name = ""
    trigger_keywords = ""
    link = ""
    
    for line in lines:
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
        elif 'TRIGGER KEYWORD:' in line:
            trigger_keywords = line.split('TRIGGER KEYWORD:')[1].strip()
        elif 'Link:' in line:
            link = line.split('Link:')[1].strip()
    
    # Count matches
    keyword_matches = 0
    matched_keywords = []
    for kw in keywords:
        if kw in trigger_keywords:
            keyword_matches += 1
            matched_keywords.append(kw)
    
    if keyword_matches > 0:
        print(f"  {form_name}")
        print(f"    Trigger keywords: {trigger_keywords[:80]}...")
        print(f"    Matched: {matched_keywords} (score: {keyword_matches}/{len(keywords)})")
        print()
