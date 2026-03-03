from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet
from .views import upload_knowledge

app_name = 'rag'

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
    # Rute utama untuk memproses upload dari form dashboard
    path('process-upload/', upload_knowledge, name='upload_document'), 
    
    # Rute lama biarkan saja jika masih dibutuhkan
    path('upload/', RedirectView.as_view(url='/dashboard/knowledge-base/', permanent=False), name='upload-knowledge-redirect'),
]