import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

# Get an ESCALATION chunk and try to extract form info
chunk = DocumentChunk.objects.filter(
    document__doc_type='ESCALATION',
    content__icontains='NAMA FORM: Acces Control Device'
).first()

if chunk:
    print("Found chunk:")
    print(chunk.content[:300])
    print("\nExtracting form info...")
    
    form_name = None
    link = None
    
    for line in chunk.content.split('\n'):
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
            print(f"  Form name: {form_name}")
        elif 'Link:' in line:
            link = line.split('Link:')[1].strip()
            print(f"  Link: {link}")
    
    print(f"\n✓ Extracted: {form_name} -> {link}")
else:
    print("No chunk found")
