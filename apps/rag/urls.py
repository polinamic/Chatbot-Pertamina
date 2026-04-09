from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter

# Semua view diimport dari apps.rag.views — JANGAN dari apps.core.views
# karena siti_chat ada di apps.rag.views, bukan apps.core
<<<<<<< Updated upstream
from .views import DocumentViewSet, upload_knowledge, siti_chat
=======
from .views import DocumentViewSet, upload_knowledge, siti_chat, get_chat_history, get_conversation_messages
>>>>>>> Stashed changes

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

    # =====================================================
    # SITI CHAT ENDPOINT
    #
    # PERBAIKAN:
    # Sebelumnya: path("api/v1/rag/chat/", views.siti_chat)
    #   → "api/v1/rag/" sudah ditambahkan oleh config/urls.py
    #   → Hasilnya URL dobel: /api/v1/rag/api/v1/rag/chat/
    #   → Import 'views' merujuk ke apps.core.views (salah)
    #
    # Sesudah: path("chat/", siti_chat)
    #   → config/urls.py tambahkan prefix → /api/v1/rag/chat/
    #   → siti_chat diimport langsung dari .views (apps.rag.views)
    # =====================================================
    path('chat/', siti_chat, name='siti_chat'),
<<<<<<< Updated upstream
=======
    
    # =====================================================
    # GET CHAT HISTORY ENDPOINT
    # GET /api/v1/rag/history/?user_id=<user_id>
    # =====================================================
    path('history/', get_chat_history, name='get_chat_history'),
    
    # =====================================================
    # GET CONVERSATION MESSAGES ENDPOINT
    # GET /api/v1/rag/conversation/<conversation_id>/messages/
    # Untuk load semua messages dari specific conversation
    # =====================================================
    path('conversation/<int:conversation_id>/messages/', get_conversation_messages, name='get_conversation_messages'),
>>>>>>> Stashed changes
]