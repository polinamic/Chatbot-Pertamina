from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'phone', 'created_at']
    list_filter = ['department', 'created_at']
    search_fields = ['user__username', 'phone']
    readonly_fields = ['created_at', 'updated_at']
