"""Common utilities for the project"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def log_activity(action, get_description=None):
    """Decorator to log user activities"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from apps.core.models import ActivityLog
            
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
            
            description = get_description(request, *args, **kwargs) if get_description else action
            
            ActivityLog.objects.create(
                action=action,
                description=description,
                user_id=request.user.id if request.user.is_authenticated else None,
                ip_address=ip_address,
            )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def api_response(status_code=status.HTTP_200_OK, message="Success", data=None):
    """Helper function to create standardized API responses"""
    response_data = {
        'status': status_code,
        'message': message,
    }
    if data is not None:
        response_data['data'] = data
    return Response(response_data, status=status_code)
