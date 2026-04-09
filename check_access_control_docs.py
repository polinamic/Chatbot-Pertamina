#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import Document, DocumentChunk

# Cari documents yang terkait Access Control / Acces
print("=" * 80)
print("CHECKING ACCESS CONTROL DOCUMENTS IN DATABASE")
print("=" * 80)

docs = Document.objects.filter(title__icontains='access')
print(f"\nTotal documents dengan 'access' dalam title: {docs.count()}")

for doc in docs:
    print(f"\n- Title: {doc.title}")
    print(f"  Category: {doc.category}")
    print(f"  Doc Type: {doc.doc_type}")
    print(f"  Is Active: {doc.is_active}")
    print(f"  Content preview: {doc.content[:150] if doc.content else 'N/A'}...")
    
    # Check chunks untuk document ini
    chunk_count = DocumentChunk.objects.filter(document=doc).count()
    print(f"  Chunks: {chunk_count}")
    
# Also search dalam content/description
print("\n" + "=" * 80)
docs_in_content = Document.objects.filter(content__icontains='access control')
print(f"Documents dengan 'access control' dalam content: {docs_in_content.count()}")

for doc in docs_in_content:
    print(f"\n- Title: {doc.title}")
    print(f"  Category: {doc.category}")
    print(f"  Doc Type: {doc.doc_type}")
    print(f"  Is Active: {doc.is_active}")

# Check semua doc_type
print("\n" + "=" * 80)
print("ALL DOCUMENT TYPES IN DATABASE:")
print("=" * 80)
from django.db.models import Count
doc_types = Document.objects.values('doc_type').annotate(count=Count('id'))
for dt in doc_types:
    print(f"- {dt['doc_type']}: {dt['count']} documents")
