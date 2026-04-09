import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import DocumentChunk

# Update trigger keywords for Access Control Device
acces_control_chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION',
    content__icontains='NAMA FORM: Acces Control Device'
)

improved_keywords = "akses, access, control, device, acs, pintu, door, kartu, card, id, ruangan, room, masuk, enter, error, tidak bisa, can't, akses kartu, kartu akses, pintu akses, access denied, denied, lock, unlock, kunci"

count = 0
for chunk in acces_control_chunks:
    # Replace old trigger keywords
    old_line = None
    for line in chunk.content.split('\n'):
        if 'TRIGGER KEYWORD:' in line:
            old_line = line
            break
    
    if old_line:
        new_content = chunk.content.replace(
            old_line,
            f"TRIGGER KEYWORD: {improved_keywords}"
        )
        chunk.content = new_content
        chunk.save()
        count += 1
        print(f"✓ Updated chunk #{chunk.id}")

print(f"\n✓ Total chunks updated: {count}")
