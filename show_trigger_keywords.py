import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

# Get all ESCALATION chunks
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
)

print("All ESCALATION Forms with Trigger Keywords:\n")

for chunk in escalation_chunks[:10]:  # Show first 10
    content = chunk.content
    lines = content.split('\n')
    
    form_name = ""
    trigger_keywords = ""
    
    for line in lines:
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
        elif 'TRIGGER KEYWORD:' in line:
            trigger_keywords = line.split('TRIGGER KEYWORD:')[1].strip()
    
    print(f"Form: {form_name}")
    print(f"Keywords: {trigger_keywords}")
    print()
