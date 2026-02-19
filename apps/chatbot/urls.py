from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet
from django.urls import path
from .views import chat_view

app_name = 'chatbot'

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')

urlpatterns = [
    # path('', include(router.urls)),
    path("", chat_view, name="chat"),
]
