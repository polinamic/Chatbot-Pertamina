import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import DocumentChunk

# Get all ESCALATION chunks
escalation_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
).order_by('chunk_index')

print(f"\n{'='*80}")
print(f"TOTAL ESCALATION FORMS: {escalation_chunks.count()}")
print(f"{'='*80}\n")

forms = {}
for chunk in escalation_chunks:
    content = chunk.content
    # Extract NAMA FORM
    if 'NAMA FORM:' in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'NAMA FORM:' in line:
                form_name = line.replace('NAMA FORM:', '').strip()
                if form_name not in forms:
                    forms[form_name] = {
                        'chunk_id': chunk.id,
                        'trigger_keywords': [],
                        'link': '',
                    }
                break
        # Extract TRIGGER_KEYWORD
        for line in lines:
            if 'TRIGGER_KEYWORD:' in line:
                keywords = line.replace('TRIGGER_KEYWORD:', '').strip()
                forms[form_name]['trigger_keywords'] = keywords.split(',')
                break
        # Extract Link
        for line in lines:
            if 'Link:' in line:
                forms[form_name]['link'] = line.replace('Link:', '').strip()
                break

print("ESCALATION FORMS IN DATABASE:\n")
for i, (form_name, data) in enumerate(forms.items(), 1):
    print(f"{i}. {form_name}")
    print(f"   Keywords: {', '.join([kw.strip() for kw in data['trigger_keywords'][:5]])}")
    print(f"   Link: {data['link'][:50]}...")
    print()
