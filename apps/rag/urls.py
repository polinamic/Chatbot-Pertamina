from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet
from .views import upload_knowledge

app_name = 'rag'

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
    path('upload/', upload_knowledge, name='upload-knowledge'),
]