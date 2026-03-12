from django.urls import path
from .views import chat_page, stream_chat

app_name = 'chatbot'

urlpatterns = [
    path('', chat_page, name='chat'),

    # Streaming AI response
    path("api/chat/stream/", stream_chat, name="stream_chat"),
]