import os, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.models import DocumentChunk

query = "wifi tamu tidak bisa konek"
query_lower = query.lower()
keywords = re.findall(r'\b\w+\b', query_lower)  # ['wifi', 'tamu', 'tidak', 'bisa', 'konek']

print("Query: " + query)
print("Keywords extracted: " + str(keywords))
print()

# Get Acces Control Device and WiFi Access forms
acces_form = DocumentChunk.objects.filter(
    content__icontains='NAMA FORM: Acces Control Device'
).first()

wifi_form = DocumentChunk.objects.filter(
    content__icontains='NAMA FORM: Wifi Access'
).first()

print("=" * 70)
print("CHECKING: Acces Control Device")
print("=" * 70)

if acces_form:
    content_lower = acces_form.content.lower()
    matched = [kw for kw in keywords if kw in content_lower]
    print("Matched keywords: " + str(matched))
    print("Score: {}/{}".format(len(matched), len(keywords)))
    
    # Show trigger keywords
    for line in acces_form.content.split('\n'):
        if 'TRIGGER KEYWORD:' in line:
            trigger = line.split('TRIGGER KEYWORD:')[1].strip()
            print("Trigger keywords: " + trigger[:100] + "...")

print()
print("=" * 70)
print("CHECKING: WiFi Access")
print("=" * 70)

if wifi_form:
    content_lower = wifi_form.content.lower()
    matched = [kw for kw in keywords if kw in content_lower]
    print("Matched keywords: " + str(matched))
    print("Score: {}/{}".format(len(matched), len(keywords)))
    
    # Show trigger keywords
    for line in wifi_form.content.split('\n'):
        if 'TRIGGER KEYWORD:' in line:
            trigger = line.split('TRIGGER KEYWORD:')[1].strip()
            print("Trigger keywords: " + trigger[:100] + "...")
        elif 'Link:' in line:
            link = line.split('Link:')[1].strip()
            is_invalid = '[link_belum_tersedia' in link.lower()
            print("Link: " + link + (" [INVALID]" if is_invalid else " [VALID]"))
