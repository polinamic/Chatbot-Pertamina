import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import Document

troubleshoot_count = Document.objects.filter(category="TROUBLESHOOT").count()
escalation_count = Document.objects.filter(category="ESCALATION").count()
total_count = Document.objects.count()

print(f"TROUBLESHOOT: {troubleshoot_count}")
print(f"ESCALATION: {escalation_count}")
print(f"Total: {total_count}")
