from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard Home
    path('', views.dashboard_home, name='index'),
    
    # Management Pages
    path('conversations/', views.conversations_management, name='conversations'),
    path('users/', views.users_management, name='users'),
    path('documents/', views.documents_management, name='documents'),
    path('analytics/', views.analytics, name='analytics'),
    
    # New Pages
    path('knowledge-base/', views.knowledge_base, name='knowledge_base'),
    path('chat-monitoring/', views.chat_monitoring, name='chat_monitoring'),
    path('audit-trail/', views.audit_trail, name='audit_trail'),
    path('system-settings/', views.system_settings, name='system_settings'),
    path('chat-detail/<int:conversation_id>/', views.chat_detail, name='chat_detail'),
    
    # API Endpoints
    path('api/stats/', views.dashboard_api_stats, name='api_stats'),
    path('api/documents/upload/', views.api_upload_document, name='api_upload_document'),
    path('api/documents/delete/<int:doc_id>/', views.api_delete_document, name='api_delete_document'),
    path('api/settings/save/', views.api_save_global_setting, name='api_save_global_setting'),
]
