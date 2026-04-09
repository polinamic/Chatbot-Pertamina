import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.models import ChatSession
from apps.rag.services.chat_service import generate_response
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService

embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)

# Create test session
session = ChatSession.objects.create(user_id=1, session_name="Test Chatbot")

# Test questions
test_questions = [
    "Bagaimana cara membuat tiket untuk kartu akses?",
    "Acces control device apa?",
    "Saya ingin membuat tiket untuk access control",
]

for question in test_questions:
    print(f"\n{'='*60}")
    print(f"Q: {question}")
    print(f"{'='*60}")
    
    response = generate_response(question, session, vector_store, embedding_service)
    
    print(f"A: {response[:500]}..." if len(response) > 500 else f"A: {response}")
    print()
