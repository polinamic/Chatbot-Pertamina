"""
Authentication decorators and utilities for protecting views
"""
from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse


def login_required_redirect(view_func):
    """
    Decorator to require login for function-based views (template views)
    Redirects to login page if user is not authenticated
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return redirect(reverse('users:login'))
        return view_func(request, *args, **kwargs)
    return wrapped_view


def admin_required_redirect(view_func):
    """
    Decorator to require admin role for function-based views
    Redirects to login page if user is not authenticated or not admin
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return redirect(reverse('users:login'))
        
        try:
            if request.user.profile.role != 'A':  # Admin role
                return redirect(reverse('chatbot:chat'))
        except:
            return redirect(reverse('users:login'))
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def get_user_or_redirect(request):
    """
    Helper function to get authenticated user or redirect to login
    Returns user if authenticated, None if not
    """
    if not request.user or not request.user.is_authenticated:
        return None
    return request.user
