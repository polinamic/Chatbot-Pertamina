from django.urls import path
from .views import chat_page, stream_chat

# Namespace is defined at config/urls.py level

# Template-based views
urlpatterns = [
    path('', chat_page, name='chat'),
]

# API endpoints (no namespace here - will be prefixed with /api/v1/chat/)
api_urlpatterns = [
    path("stream/", stream_chat, name="stream_chat"),
]