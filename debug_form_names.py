"""Debug script to check form name matching in database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import DocumentChunk

# Get all ESCALATION chunks and extract form names
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
).order_by('chunk_index')

print("FORM NAMES IN DATABASE:\n")

form_names = set()
for chunk in escalation_chunks:
    content = chunk.content
    if 'NAMA FORM:' in content:
        lines = content.split('\n')
        for line in lines:
            if 'NAMA FORM:' in line:
                form_name = line.replace('NAMA FORM:', '').strip()
                form_names.add(form_name)
                break

for i, name in enumerate(sorted(form_names), 1):
    print(f"{i}. {name}")

print(f"\nTotal: {len(form_names)} unique forms")

# Now check which ones we're looking for
print("\n" + "="*80)
print("CHECKING AGAINST OUR CATEGORY_FORMS MAPPING:")
print("="*80 + "\n")

from apps.rag.services.chat_service import CATEGORY_FORMS

for category, forms in CATEGORY_FORMS.items():
    print(f"\n{category}:")
    for form in forms:
        found = form in form_names
        status = "✓" if found else "✗"
        print(f"  {status} {form}")
