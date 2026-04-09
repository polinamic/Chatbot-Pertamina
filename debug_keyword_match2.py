import os, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

query = "akses pintu masuk ruangan saya error nih"
query_lower = query.lower()
keywords = re.findall(r'\b\w+\b', query_lower)

print(f"Query: {query}")
print(f"Keywords extracted: {keywords}\n")

# Get all ESCALATION chunks
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
)

print("Checking each form:\n")
for chunk in escalation_chunks[:5]:
    content = chunk.content.lower()
    
    # Extract form name and trigger keywords
    form_name = ""
    trigger_keywords = ""
    for line in chunk.content.split('\n'):
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
        elif 'TRIGGER KEYWORD:' in line:
            trigger_keywords = line.split('TRIGGER KEYWORD:')[1].strip()
    
    # Count matches
    keyword_matches = sum(1 for kw in keywords if kw in content)
    
    print(f"✓ Form: {form_name}")
    print(f"  Trigger Keywords: {trigger_keywords}")
    print(f"  Match Score: {keyword_matches}/{len(keywords)}")
    
    # Show which keywords matched
    matched = [kw for kw in keywords if kw in content]
    print(f"  Matched keywords: {matched}")
    print()
