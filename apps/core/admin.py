from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'description', 'user_id', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['description']
    readonly_fields = ['created_at']
