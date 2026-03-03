import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Document

docs = Document.objects.all()
print(f"✓ Total Documents: {docs.count()}")
if docs.exists():
    latest = Document.objects.order_by('-id').first()
    print(f"✓ Latest: {latest.file_name} (ID: {latest.id}, processed={latest.is_processed})")
