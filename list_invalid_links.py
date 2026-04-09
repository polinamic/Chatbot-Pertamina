import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

# Get all ESCALATION chunks with invalid links
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
)

invalid_forms = []

for chunk in escalation_chunks:
    form_name = None
    link = None
    
    for line in chunk.content.split('\n'):
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
        elif 'Link:' in line:
            link = line.split('Link:')[1].strip()
    
    # Check if link is invalid placeholder
    if link and ('[link_belum_tersedia' in link.lower() or 'not available' in link.lower()):
        invalid_forms.append({
            'form': form_name,
            'link': link,
            'chunk_id': chunk.id
        })

print("=" * 80)
print("FORMS DENGAN INVALID/PLACEHOLDER LINKS (PERLU DIPERBAIKI)")
print("=" * 80)
print()

if invalid_forms:
    for i, form in enumerate(invalid_forms, 1):
        print(f"{i}. {form['form']}")
        print(f"   Link saat ini: {form['link']}")
        print(f"   Chunk ID: {form['chunk_id']}")
        print()
    
    print("=" * 80)
    print(f"SUMMARY: {len(invalid_forms)} forms perlu diperbaiki")
    print("=" * 80)
    print()
    print("ACTION: Update link untuk forms di atas dengan URL yang valid")
    print("Example URL: https://myssc.pertamina.com/dwp/app/#/itemprofile/[ID]")
else:
    print("Tidak ada forms dengan invalid links. Semua baik!")
