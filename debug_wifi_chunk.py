"""Debug: Check form chunk content"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import DocumentChunk

# Get WiFi Access form
chunks = DocumentChunk.objects.select_related('document').filter(
    document__doc_type='ESCALATION'
)

for chunk in chunks:
    content = chunk.content
    if 'Wifi Access' in content or 'NAMA FORM:' in content and 'Wifi' in content:
        print("="*80)
        print("WIFI ACCESS FORM CHUNK:")
        print("="*80)
        print(content[:500])
        print("\n" + "="*80)
        print("Full chunk length:", len(content))
        print("="*80)
        
        # Check which keywords appear in the content
        query = "wifi tidak bisa konek di kantor"
        keywords = ["wifi", "tidak", "bisa", "konek", "di", "kantor"]
        print(f"\nQuery: {query}")
        print("Keywords found in chunk:")
        for kw in keywords:
            if kw in content.lower():
                print(f"  ✓ {kw}")
            else:
                print(f"  ✗ {kw}")
        break
