import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.getcwd())
from apps.rag.services.chat_service import detect_intent
print(detect_intent('koneksi internet saya tidak stabil kadang bisa tersambung kadang terputus, bagaimana cara memperbaikinya'))
print(detect_intent('wifi saya tidak bisa konek'))
print(detect_intent('siapa pencipta wifi'))
