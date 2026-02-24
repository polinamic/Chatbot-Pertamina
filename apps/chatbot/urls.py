from django.urls import path
from .views import chat_page

app_name = 'chatbot'

urlpatterns = [
    path('', chat_page, name='chat'),
]
