from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter

# --- PERBAIKAN 1: Tambahkan send_message ke dalam import ---
from .views import DocumentViewSet, upload_knowledge, siti_chat, get_chat_history, get_conversation_messages, send_message

app_name = 'rag'

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),

    # Upload dokumen knowledge base dari form dashboard
    path('process-upload/', upload_knowledge, name='upload_document'),

    # Redirect rute lama ke dashboard
    path('upload/', RedirectView.as_view(
        url='/dashboard/knowledge-base/', permanent=False
    ), name='upload-knowledge-redirect'),

    # SITI CHAT ENDPOINT
    path('chat/', siti_chat, name='siti_chat'),
    
    # GET CHAT HISTORY ENDPOINT
    path('history/', get_chat_history, name='get_chat_history'),
    
    # GET CONVERSATION MESSAGES ENDPOINT
    path('conversation/<int:conversation_id>/messages/', get_conversation_messages, name='get_conversation_messages'),
    
    # --- PERBAIKAN 2: Tambahkan path untuk send_message ---
    path('conversations/<int:conversation_id>/send_message/', send_message, name='send_message'),
]