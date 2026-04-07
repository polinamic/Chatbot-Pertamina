"""
Role-based permission classes untuk access control
"""
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission class untuk hanya admin yang bisa akses
    """
    message = "Hanya admin yang bisa mengakses resource ini"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super user (staff) adalah admin
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Check UserProfile role
        try:
            profile = request.user.profile
            return profile.role == 'A'  # Admin role
        except:
            return False


class IsUser(permissions.BasePermission):
    """
    Permission class untuk regular users
    """
    message = "Hanya registered users yang bisa mengakses resource ini"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.profile
            return profile.role == 'U'  # User role
        except:
            return False


class IsSupport(permissions.BasePermission):
    """
    Permission class untuk support staff
    """
    message = "Hanya support staff yang bisa mengakses resource ini"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.profile
            return profile.role in ['S', 'A']  # Support atau Admin
        except:
            return False


class IsManager(permissions.BasePermission):
    """
    Permission class untuk managers
    """
    message = "Hanya managers yang bisa mengakses resource ini"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.profile
            return profile.role in ['M', 'A']  # Manager atau Admin
        except:
            return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Admin bisa edit/delete, user lain hanya read
    """
    message = "Hanya admin yang bisa mengubah resource ini"
    
    def has_permission(self, request, view):
        # Allow read-only access untuk semua
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write access hanya untuk admin
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        try:
            profile = request.user.profile
            return profile.role == 'A'
        except:
            return False


class IsUserOrAdmin(permissions.BasePermission):
    """
    User bisa access resource mereka sendiri, admin bisa access semua
    """
    message = "Anda tidak punya akses ke resource ini"
    
    def has_object_permission(self, request, view, obj):
        # Admin bisa access semua
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        try:
            profile = request.user.profile
            if profile.role == 'A':
                return True
        except:
            pass
        
        # User hanya bisa access resource mereka sendiri
        # Misalnya conversation miliknya, atau document yang dia upload
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'uploaded_by'):
            return obj.uploaded_by == request.user
        
        return False
