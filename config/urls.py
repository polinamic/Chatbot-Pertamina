"""
URL configuration for chatbot_pertamina project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/chatbot/', include('apps.chatbot.urls', namespace='chatbot')),
    path('api/v1/rag/', include('apps.rag.urls', namespace='rag')),
    path('api/v1/users/', include('apps.users.urls', namespace='users')),
    path('api-auth/', include('rest_framework.urls')),
    path("chat/", include("apps.chatbot.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
