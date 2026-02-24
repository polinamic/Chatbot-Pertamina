"""
URL configuration for chatbot_pertamina project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from apps.users.views import UserViewSet
from apps.chatbot.views import ConversationViewSet

# API Router
api_router = DefaultRouter()
api_router.register(r'users', UserViewSet, basename='api-user')
api_router.register(r'conversations', ConversationViewSet, basename='api-conversation')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Template views (non-API routes)
    path('auth/', include('apps.users.urls')),
    path('', include('apps.chatbot.urls')),
    
    # API routes
    path('api/v1/', include(api_router.urls)),
    path('api/v1/rag/', include('apps.rag.urls')),
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
