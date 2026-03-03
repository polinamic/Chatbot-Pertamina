"""
Authentication middleware untuk token-based authentication
"""
import jwt
import logging
from django.http import JsonResponse
from django.utils.decorators import sync_and_async_middleware
from decouple import config

logger = logging.getLogger(__name__)


class JWTAuthenticationMiddleware:
    """
    Middleware untuk validasi JWT token pada setiap request
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.secret_key = config('SECRET_KEY', default='django-insecure-change-me-in-production')

    def __call__(self, request):
        # Skip authentication untuk endpoint publik
        public_paths = ['/api/auth/login/', '/api/auth/signup/', '/api/auth/refresh/']
        
        if request.path in public_paths or request.method == 'OPTIONS':
            return self.get_response(request)

        # Ambil token dari Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Hapus "Bearer " prefix
            try:
                # Decode token
                payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
                request.user_id = payload.get('user_id')
                request.token = token
            except jwt.ExpiredSignatureError:
                logger.warning(f"Expired token from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({
                    'error': 'Token expired',
                    'code': 'TOKEN_EXPIRED'
                }, status=401)
            except jwt.InvalidTokenError:
                logger.warning(f"Invalid token from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({
                    'error': 'Invalid token',
                    'code': 'INVALID_TOKEN'
                }, status=401)

        response = self.get_response(request)
        return response


class ActivityLogMiddleware:
    """
    Middleware untuk mencatat aktivitas user
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ambil user_id dari request (set oleh JWTAuthenticationMiddleware)
        user_id = getattr(request, 'user_id', None)
        ip_address = self.get_client_ip(request)
        
        # Logging untuk berbagai aksi
        if request.method == 'POST' and request.path.startswith('/api/auth/login'):
            logger.info(f"User login attempt from {ip_address}")
        elif request.method == 'POST' and request.path.startswith('/api/auth/signup'):
            logger.info(f"User signup from {ip_address}")
        elif user_id and request.method == 'GET':
            logger.info(f"User {user_id} viewed {request.path}")

        response = self.get_response(request)
        return response

    @staticmethod
    def get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CORSMiddleware:
    """
    Simple CORS middleware untuk development
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add CORS headers
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        if request.method == 'OPTIONS':
            response.status_code = 200
        
        return response
