from rest_framework import viewsets, status, views
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from django.utils import timezone
import jwt
import logging

from .models import UserProfile, UserSettings, PasswordResetToken
from .serializers import (
    UserSerializer, 
    UserProfileSerializer, 
    UserSignupSerializer,
    UserLoginSerializer,
    TokenRefreshSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from .token_manager import TokenManager
from .email_service import EmailService
from apps.core.models import ActivityLog
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

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
    """
    Handle signup page - form-based signup
    """
    from django.shortcuts import render, redirect
    from django.contrib.auth import authenticate, login as auth_login # PERBAIKAN: Import yang terlupa
    
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
            
            # PERBAIKAN: Gunakan get_or_create untuk mencegah bentrok dengan signals.py
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.company = 'Pertamina'
            profile.save()
            
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


def profile_page(request):
    """
    Display and edit user profile
    PROTECTED: Requires authentication
    """
    from django.shortcuts import render, redirect
    from apps.users.decorators import login_required_redirect
    from django.contrib import messages  # <-- Import tambahan untuk sistem notifikasi
    
    @login_required_redirect
    def _profile_page(request):
        user = request.user
        
        if request.method == 'POST':
            # Update profile
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            bio = request.POST.get('bio', '').strip()
            department = request.POST.get('department', 'OTHER')
            company = request.POST.get('company', '').strip()
            
            try:
                # Update user
                user.first_name = first_name
                user.last_name = last_name
                user.save()
                
                # Update profile
                profile = user.profile
                profile.phone = phone
                profile.bio = bio
                profile.department = department
                profile.company = company
                profile.save()
                
                # Log activity
                ActivityLog.objects.create(
                    action='UPDATE',
                    description=f'User {user.email} updated profile',
                    user_id=str(user.id)
                )
                
                # ---> PERBAIKAN PRG PATTERN DI SINI <---
                messages.success(request, '✅ Profil berhasil diperbarui!')
                return redirect('users:profile') # Alihkan halaman, bukan dirender
                
            except Exception as e:
                logger.error(f"Profile update error: {str(e)}", exc_info=True)
                
                # ---> PERBAIKAN PRG PATTERN DI SINI <---
                messages.error(request, f'Error: {str(e)}')
                return redirect('users:profile') # Alihkan halaman, bukan dirender
        
        # Render normal untuk method GET
        return render(request, 'users/profile.html', {
            'user': user,
            'profile': user.profile,
        })
    
    return _profile_page(request)


def settings_page(request):
    """
    Display and edit user settings
    ✅ PROTECTED: Requires authentication
    Each user has their own settings stored in database
    """
    from django.shortcuts import render
    from apps.users.decorators import login_required_redirect
    
    @login_required_redirect
    def _settings_page(request):
        user = request.user
        
        # Get or create user settings
        settings, created = UserSettings.objects.get_or_create(user=user)
        
        if request.method == 'POST':
            # Update settings
            theme = request.POST.get('theme', 'auto')
            language = request.POST.get('language', 'id')
            enable_notifications = request.POST.get('enable_notifications') == 'on'
            enable_history_logging = request.POST.get('enable_history_logging') == 'on'
            receive_email_updates = request.POST.get('receive_email_updates') == 'on'
            is_profile_public = request.POST.get('is_profile_public') == 'on'
            
            try:
                settings.theme = theme
                settings.language = language
                settings.enable_notifications = enable_notifications
                settings.enable_history_logging = enable_history_logging
                settings.receive_email_updates = receive_email_updates
                settings.is_profile_public = is_profile_public
                settings.save()
                
                # Log activity
                ActivityLog.objects.create(
                    action='UPDATE',
                    description=f'User {user.email} updated settings',
                    user_id=str(user.id)
                )
                
                return render(request, 'users/settings.html', {
                    'user': user,
                    'settings': settings,
                    'success': '✅ Pengaturan berhasil disimpan!'
                })
            except Exception as e:
                logger.error(f"Settings update error: {str(e)}", exc_info=True)
                return render(request, 'users/settings.html', {
                    'user': user,
                    'settings': settings,
                    'error': f'Error: {str(e)}'
                })
        
        return render(request, 'users/settings.html', {
            'user': user,
            'settings': settings,
        })
    
    return _settings_page(request)


class ForgotPasswordView(views.APIView):
    """
    API endpoint untuk request password reset
    POST /api/auth/forgot-password/
    
    Endpoint ini menerima email dan:
    1. Generate secure random token
    2. Simpan token hash di database dengan expiry
    3. Kirim email reset link ke user
    
    Security: Selalu return success message apakah email ditemukan atau tidak
    (mencegah email enumeration)
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                # Find user by email
                user = User.objects.get(email=email)
                
                # Create password reset token
                plain_token, reset_token = PasswordResetToken.create_for_user(
                    user, 
                    expiry_minutes=15
                )
                
                # Build reset link
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                reset_link = f"{frontend_url}/auth/reset-password?token={plain_token}"
                
                # Send email
                email_sent = EmailService.send_password_reset_email(
                    user.email,
                    reset_link,
                    token_expiry_minutes=15
                )
                
                if email_sent:
                    logger.info(f"Password reset email sent to {user.email}")
                else:
                    logger.warning(f"Failed to send password reset email to {user.email}")
                
                # Log activity
                ActivityLog.objects.create(
                    action='FORGOT_PASSWORD',
                    description=f'Password reset requested for {user.email}',
                    user_id=str(user.id),
                    ip_address=self.get_client_ip(request)
                )
                
            except User.DoesNotExist:
                # Security best practice: Don't reveal if email exists
                logger.info(f"Password reset requested for non-existent email: {email}")
                pass
            except Exception as e:
                logger.error(f"Error in forgot password: {str(e)}", exc_info=True)
            
            # Always return generic success message (security best practice)
            return Response({
                'message': 'Jika email terdaftar, link reset password telah dikirim ke email Anda. Silakan cek inbox atau folder spam Anda.',
                'code': 'PASSWORD_RESET_EMAIL_SENT'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ResetPasswordView(views.APIView):
    """
    API endpoint untuk reset password dengan token
    POST /api/auth/reset-password/
    
    Endpoint ini:
    1. Validasi token (ada, tidak expired, tidak used)
    2. Update password user
    3. Tandai token sebagai used
    4. Kirim confirmation email
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']
            
            try:
                # Validate token and get user
                user, reset_token = PasswordResetToken.get_user_from_token(token)
                
                if not user or not reset_token:
                    return Response({
                        'error': 'Token tidak valid atau sudah kadaluarsa',
                        'code': 'INVALID_TOKEN'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Check token validity
                if not reset_token.is_valid():
                    if reset_token.is_used:
                        return Response({
                            'error': 'Token sudah digunakan',
                            'code': 'TOKEN_ALREADY_USED'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({
                            'error': 'Token sudah kadaluarsa',
                            'code': 'TOKEN_EXPIRED'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Update user password
                user.set_password(new_password)
                user.save()
                
                # Mark token as used
                reset_token.mark_as_used()
                
                # Send confirmation email
                EmailService.send_password_changed_confirmation_email(user.email)
                
                # Log activity
                ActivityLog.objects.create(
                    action='RESET_PASSWORD',
                    description=f'Password reset completed for {user.email}',
                    user_id=str(user.id),
                    ip_address=self.get_client_ip(request)
                )
                
                logger.info(f"Password successfully reset for {user.email}")
                
                return Response({
                    'message': 'Password berhasil diubah. Silakan login dengan password baru Anda.',
                    'code': 'PASSWORD_RESET_SUCCESS'
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Error in reset password: {str(e)}", exc_info=True)
                return Response({
                    'error': 'Terjadi kesalahan saat mereset password',
                    'code': 'RESET_PASSWORD_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Template Views for Web Pages
def forgot_password_page(request):
    """
    Handle forgot password page
    GET: Display form
    POST: Process forgot password request
    """
    from django.shortcuts import render
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            return render(request, 'users/forgot_password.html', {
                'error': 'Email wajib diisi'
            })
        
        try:
            # Find user
            user = User.objects.get(email=email)
            
            # Create password reset token
            plain_token, reset_token = PasswordResetToken.create_for_user(
                user,
                expiry_minutes=15
            )
            
            # Build reset link
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            reset_link = f"{frontend_url}/auth/reset-password?token={plain_token}"
            
            # Send email
            email_sent = EmailService.send_password_reset_email(
                user.email,
                reset_link,
                token_expiry_minutes=15
            )
            
            # Log activity
            ActivityLog.objects.create(
                action='FORGOT_PASSWORD',
                description=f'Password reset requested for {user.email}',
                user_id=str(user.id),
                ip_address=get_client_ip(request)
            )
            
            # Show success message
            return render(request, 'users/forgot_password.html', {
                'success': True,
                'message': 'Jika email terdaftar, link reset password telah dikirim ke email Anda. Silakan cek inbox atau folder spam Anda.'
            })
            
        except User.DoesNotExist:
            # Don't reveal if email exists (security best practice)
            return render(request, 'users/forgot_password.html', {
                'success': True,
                'message': 'Jika email terdaftar, link reset password telah dikirim ke email Anda. Silakan cek inbox atau folder spam Anda.'
            })
        except Exception as e:
            logger.error(f"Forgot password error: {str(e)}", exc_info=True)
            return render(request, 'users/forgot_password.html', {
                'error': 'Terjadi kesalahan. Silakan coba lagi nanti.'
            })
    
    return render(request, 'users/forgot_password.html')


def reset_password_page(request):
    """
    Handle reset password page
    GET: Display form (validate token first)
    POST: Process password reset
    """
    from django.shortcuts import render, redirect
    
    if request.method == 'GET':
        token = request.GET.get('token', '')
        
        if not token:
            return render(request, 'users/reset_password.html', {
                'error': 'Token tidak ditemukan'
            })
        
        # Validate token
        user, reset_token = PasswordResetToken.get_user_from_token(token)
        
        if not user or not reset_token:
            return render(request, 'users/reset_password.html', {
                'error': 'Token tidak valid atau sudah kadaluarsa'
            })
        
        if not reset_token.is_valid():
            if reset_token.is_used:
                return render(request, 'users/reset_password.html', {
                    'error': 'Token sudah digunakan'
                })
            else:
                return render(request, 'users/reset_password.html', {
                    'error': 'Token sudah kadaluarsa'
                })
        
        # Token valid, show form
        return render(request, 'users/reset_password.html', {
            'token': token,
            'token_valid': True
        })
    
    if request.method == 'POST':
        token = request.POST.get('token', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        errors = {}
        
        # Validation
        if not token:
            errors['token'] = 'Token tidak ditemukan'
        
        if not new_password:
            errors['new_password'] = 'Password baru wajib diisi'
        elif len(new_password) < 8:
            errors['new_password'] = 'Password minimal 8 karakter'
        elif not any(char.isupper() for char in new_password):
            errors['new_password'] = 'Password harus mengandung minimal 1 huruf besar'
        elif not any(char.isdigit() for char in new_password):
            errors['new_password'] = 'Password harus mengandung minimal 1 angka'
        
        if new_password != confirm_password:
            errors['confirm_password'] = 'Password tidak cocok'
        
        # Validate token
        user, reset_token = PasswordResetToken.get_user_from_token(token)
        
        if not user or not reset_token:
            errors['token'] = 'Token tidak valid atau sudah kadaluarsa'
        elif not reset_token.is_valid():
            if reset_token.is_used:
                errors['token'] = 'Token sudah digunakan'
            else:
                errors['token'] = 'Token sudah kadaluarsa'
        
        if errors:
            return render(request, 'users/reset_password.html', {
                'errors': errors,
                'token': token
            })
        
        try:
            # Update password
            user.set_password(new_password)
            user.save()
            
            # Mark token as used
            reset_token.mark_as_used()
            
            # Send confirmation email
            EmailService.send_password_changed_confirmation_email(user.email)
            
            # Log activity
            ActivityLog.objects.create(
                action='RESET_PASSWORD',
                description=f'Password reset completed for {user.email}',
                user_id=str(user.id),
                ip_address=get_client_ip(request)
            )
            
            return render(request, 'users/reset_password.html', {
                'success': True,
                'message': 'Password berhasil diubah. Silakan login dengan password baru Anda.'
            })
            
        except Exception as e:
            logger.error(f"Reset password error: {str(e)}", exc_info=True)
            return render(request, 'users/reset_password.html', {
                'errors': {'general': 'Terjadi kesalahan saat mereset password'},
                'token': token
            })
    
    return render(request, 'users/reset_password.html')


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

