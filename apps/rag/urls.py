from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter

# Semua view diimport dari apps.rag.views
from .views import DocumentViewSet, upload_knowledge, siti_chat, get_chat_history, get_conversation_messages

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
]