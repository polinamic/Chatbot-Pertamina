import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

# Get all ESCALATION chunks and check their links
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
)

print("=" * 80)
print("AUDIT: Semua ESCALATION Forms dan Links")
print("=" * 80)

forms_data = []

for chunk in escalation_chunks:
    form_name = None
    link = None
    trigger_keywords = None
    
    for line in chunk.content.split('\n'):
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
        elif 'Link:' in line:
            link = line.split('Link:')[1].strip()
        elif 'TRIGGER KEYWORD:' in line:
            trigger_keywords = line.split('TRIGGER KEYWORD:')[1].strip()
    
    forms_data.append({
        'form': form_name,
        'link': link,
        'keywords': trigger_keywords,
        'chunk_id': chunk.id
    })

# Print dengan format table
print("\nNo. | NAMA FORM | LINK | KEYWORDS (First 50 chars)")
print("-" * 80)

for i, data in enumerate(forms_data, 1):
    form = data['form'] or "MISSING"
    link = data['link'] or "MISSING"
    keywords = (data['keywords'][:50] + "...") if data['keywords'] else "MISSING"
    
    # Add warning if link is missing
    warning = " [ERROR!]" if not data['link'] else ""
    
    print(f"{i:2}. | {form:30} | {link[:40]:40} | {keywords}")
    if not data['link']:
        print(f"    ERROR: Link tidak ada untuk form: {form}")
    print()

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)

missing_links = [d for d in forms_data if not d['link']]
missing_forms = [d for d in forms_data if not d['form']]

print(f"Total ESCALATION forms: {len(forms_data)}")
print(f"Forms dengan LINK: {len(forms_data) - len(missing_links)}")
print(f"Forms TANPA LINK: {len(missing_links)} {' [WARNING!]' if missing_links else ''}")
print(f"Forms tanpa nama: {len(missing_forms)} {' [ERROR!]' if missing_forms else ''}")

if missing_links:
    print(f"\nForms yang HARUS diperbaiki:")
    for d in missing_links:
        print(f"  - {d['form']} (Chunk ID: {d['chunk_id']})")
