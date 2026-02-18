from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk melihat activity logs
    """
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['action', 'user_id']
    ordering = ['-created_at']
