from rest_framework import serializers
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ['id', 'action', 'description', 'user_id', 'ip_address', 'created_at']
        read_only_fields = ['id', 'created_at']
