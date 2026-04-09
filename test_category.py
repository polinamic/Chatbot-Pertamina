import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

#Suppress logs
import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import detect_problem_category

query = "Mas/Mbak, akses pintu masuk ruangan saya error nih kartu ID-"
category = detect_problem_category(query.lower())

print(f"Query: {query}")
print(f"Detected category: {category}")
