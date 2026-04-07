from rest_framework import viewsets, status, views
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from django.utils import timezone
import jwt
import logging

from .models import UserProfile
from .serializers import (
    UserSerializer, 
    UserProfileSerializer, 
    UserSignupSerializer,
    UserLoginSerializer,
    TokenRefreshSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer
)
from .token_manager import TokenManager
from apps.core.models import ActivityLog

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk mengelola users (API endpoints)
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'username'

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action == 'create':
            return [AllowAny()]
        elif self.action == 'retrieve' and self.kwargs.get('username') == 'me':
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Return serializer class based on action"""
        if self.action == 'create':
            return UserSignupSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return UserUpdateSerializer
        elif self.action == 'change_password':
            return ChangePasswordSerializer
        return UserSerializer

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current user profile"""
        try:
            user = request.user
            if not user or not user.is_authenticated:
                return Response({
                    'error': 'User tidak ditemukan'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({
                'error': 'User tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['put'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """Update current user profile"""
        try:
            user = request.user
            if not user or not user.is_authenticated:
                return Response({
                    'error': 'User tidak ditemukan'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = UserUpdateSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                # Log activity
                ActivityLog.objects.create(
                    action='UPDATE',
                    description=f'User {user.email or user.username} updated profile',
                    user_id=str(user.id),
                    ip_address=self.get_client_ip(request)
                )
                
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({
                'error': 'User tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        """Change user password"""
        try:
            user = request.user
            if not user or not user.is_authenticated:
                return Response({
                    'error': 'User tidak ditemukan'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = ChangePasswordSerializer(data=request.data)
            
            if serializer.is_valid():
                # Verify old password
                if not user.check_password(serializer.validated_data['old_password']):
                    return Response({
                        'error': 'Password lama salah'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Set new password
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                
                # Log activity
                ActivityLog.objects.create(
                    action='UPDATE',
                    description=f'User {user.email or user.username} changed password',
                    user_id=str(user.id),
                    ip_address=self.get_client_ip(request)
                )
                
                return Response({
                    'message': 'Password berhasil diubah'
                })
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({
                'error': 'User tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)

    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SignupView(views.APIView):
    """
    API endpoint untuk signup user
    POST /api/auth/signup/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserSignupSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Log activity
            ActivityLog.objects.create(
                action='CREATE',
                description=f'New user registered: {user.email}',
                user_id=str(user.id),
                ip_address=self.get_client_ip(request)
            )
            
            # Generate tokens
            tokens = TokenManager.generate_tokens(str(user.id), user.email)
            
            return Response({
                'message': 'Signup berhasil',
                'user': UserSerializer(user).data,
                **tokens
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LoginView(views.APIView):
    """
    API endpoint untuk login user
    POST /api/auth/login/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Update last login
            user.last_login = timezone.now()
            user.save()
            
            # Log activity
            ActivityLog.objects.create(
                action='LOGIN',
                description=f'User {user.email or user.username} logged in',
                user_id=str(user.id),
                ip_address=self.get_client_ip(request)
            )
            
            # Generate tokens
            tokens = TokenManager.generate_tokens(str(user.id), user.email)
            
            return Response({
                'message': 'Login berhasil',
                'user': UserSerializer(user).data,
                **tokens
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RefreshTokenView(views.APIView):
    """
    API endpoint untuk refresh access token
    POST /api/auth/refresh/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                tokens = TokenManager.refresh_access_token(
                    serializer.validated_data['refresh_token']
                )
                return Response(tokens, status=status.HTTP_200_OK)
            except jwt.ExpiredSignatureError:
                return Response({
                    'error': 'Refresh token expired',
                    'code': 'TOKEN_EXPIRED'
                }, status=status.HTTP_401_UNAUTHORIZED)
            except jwt.InvalidTokenError:
                return Response({
                    'error': 'Invalid refresh token',
                    'code': 'INVALID_TOKEN'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(views.APIView):
    """
    API endpoint untuk logout user
    POST /api/auth/logout/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if not user or not user.is_authenticated:
            return Response({
                'error': 'User tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Log activity
        ActivityLog.objects.create(
            action='LOGOUT',
            description=f'User {user.email or user.username} logged out',
            user_id=str(user.id),
            ip_address=self.get_client_ip(request)
        )
        
        return Response({
            'message': 'Logout berhasil'
        }, status=status.HTTP_200_OK)
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Template Views (untuk backward compatibility)
def signup_page(request):
    """Handle signup page - form-based signup"""
    from django.shortcuts import render, redirect
    from django.contrib.auth import authenticate, login as auth_login
    
    if request.method == 'GET':
        return render(request, 'users/signup.html')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        
        errors = {}
        
        # Validation
        if not username or len(username) < 3:
            errors['username'] = 'Username harus minimal 3 karakter'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'Username sudah digunakan'
        
        if not email:
            errors['email'] = 'Email wajib diisi'
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'Email sudah terdaftar'
        
        if not password or len(password) < 8:
            errors['password'] = 'Password minimal 8 karakter'
        elif not any(char.isupper() for char in password):
            errors['password'] = 'Password harus mengandung minimal 1 huruf besar'
        elif not any(char.isdigit() for char in password):
            errors['password'] = 'Password harus mengandung minimal 1 angka'
        
        if errors:
            return render(request, 'users/signup.html', {
                'errors': errors,
                'username': username,
                'email': email
            })
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Create user profile
            profile = UserProfile.objects.create(
                user=user,
                company='Pertamina'
            )
            
            # Log activity
            ActivityLog.objects.create(
                action='CREATE',
                description=f'New user registered via web form: {email}',
                user_id=str(user.id)
            )
            
            # Auto-login user
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('chatbot:chat')
            else:
                return redirect('users:login')
                
        except Exception as e:
            logger.error(f"Signup error: {str(e)}", exc_info=True)
            errors['general'] = f'Terjadi kesalahan saat membuat akun: {str(e)}'
            return render(request, 'users/signup.html', {
                'errors': errors,
                'username': username,
                'email': email
            })
    
    return render(request, 'users/signup.html')


def login_page(request):
    """Handle login page"""
    from django.shortcuts import render, redirect
    from django.contrib.auth import authenticate, login as auth_login
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            user.last_login = timezone.now()
            user.save()
            
            # Log activity
            ActivityLog.objects.create(
                action='LOGIN',
                description=f'User {user.email or user.username} logged in via web form',
                user_id=str(user.id)
            )
            
            auth_login(request, user)
            
            # Redirect based on user role
            try:
                profile = user.profile
                if profile.role == 'A':  # Admin
                    return redirect('dashboard:index')
                else:  # User, Support, Manager
                    return redirect('chatbot:chat')
            except UserProfile.DoesNotExist:
                # Default to chatbot if profile not found
                return redirect('chatbot:chat')
        else:
            return render(request, 'users/login.html', {
                'error': 'Username atau password salah'
            })
    
    return render(request, 'users/login.html')


def logout_page(request):
    """Handle logout"""
    from django.shortcuts import redirect
    from django.contrib.auth import logout
    
    if request.user and request.user.is_authenticated:
        ActivityLog.objects.create(
            action='LOGOUT',
            description=f'User {request.user.email or request.user.username} logged out via web form',
            user_id=str(request.user.id)
        )
    
    logout(request)
    return redirect('users:login')
