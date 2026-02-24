from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import UserProfile
from .serializers import UserSerializer, UserProfileSerializer, UserRegistrationSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk mengelola users
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        return UserSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['put'])
    def update_profile(self, request):
        """Update current user profile"""
        user_profile = request.user.profile
        serializer = UserProfileSerializer(user_profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Template Views
def signup_page(request):
    """Handle signup page"""
    if request.method == 'POST':
        email = request.POST.get('email', '')
        username = request.POST.get('username', email.split('@')[0])
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validation
        if password != confirm_password:
            return render(request, 'users/signup.html', {
                'error': 'Password tidak cocok',
                'email': email,
                'username': username
            })
        
        if User.objects.filter(username=username).exists():
            return render(request, 'users/signup.html', {
                'error': 'Username sudah digunakan',
                'email': email
            })
        
        if User.objects.filter(email=email).exists():
            return render(request, 'users/signup.html', {
                'error': 'Email sudah terdaftar',
                'username': username
            })
        
        # Create user
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect('dashboard:index')
        except Exception as e:
            return render(request, 'users/signup.html', {
                'error': str(e),
                'email': email,
                'username': username
            })
    
    return render(request, 'users/signup.html')


def login_page(request):
    """Handle login page"""
    if request.method == 'POST':
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        
        try:
            # Try to find user by email
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'dashboard:index')
                if next_url.startswith('/'):
                    return redirect(next_url)
                return redirect(next_url)
            else:
                return render(request, 'users/login.html', {
                    'error': 'Email atau password salah'
                })
        except User.DoesNotExist:
            return render(request, 'users/login.html', {
                'error': 'Email tidak terdaftar'
            })
    
    return render(request, 'users/login.html')


@login_required(login_url='/auth/login/')
def logout_page(request):
    """Handle logout"""
    logout(request)
    return redirect('users:login')
