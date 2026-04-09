"""
URL configuration for chatbot_pertamina project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework.routers import DefaultRouter

from apps.users.views import UserViewSet
from apps.users.urls import api_urlpatterns as users_api_urls
from apps.chatbot.views import ConversationViewSet
from apps.chatbot.urls import api_urlpatterns as chatbot_api_urls


# ==============================
# API Router
# ==============================

api_router = DefaultRouter()
api_router.register(r'users', UserViewSet, basename='api-user')
api_router.register(r'conversations', ConversationViewSet, basename='api-conversation')


# ==============================
# URL PATTERNS
# ==============================

urlpatterns = [

    # Admin
    path('admin/', admin.site.urls),

    # ==============================
    # Template Views (Non-API)
    # ==============================

    path('auth/', include('apps.users.urls')),
    path('', include(('apps.chatbot.urls', 'chatbot'))),
    path('dashboard/', include('apps.dashboard.urls')),


    # ==============================
    # API Routes
    # ==============================

    path('api/v1/users/', include(users_api_urls)),
    path('api/v1/', include(api_router.urls)),
    path('api/v1/rag/', include('apps.rag.urls')),
    path('api/v1/chat/', include(chatbot_api_urls)),
    path('api-auth/', include('rest_framework.urls')),
]


# ==============================
# Static & Media (Development)
# ==============================

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)