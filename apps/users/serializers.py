from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile
import re


class EmailField(serializers.EmailField):
    """Custom email field with validation"""
    def to_representation(self, value):
        return value.lower() if value else value


class UserProfileSerializer(serializers.ModelSerializer):
    """User profile serializer"""
    class Meta:
        model = UserProfile
        fields = ['id', 'role', 'department', 'company', 'phone', 'bio', 'is_verified']
        read_only_fields = ['id']


class UserSerializer(serializers.ModelSerializer):
    """User serializer untuk GET operations"""
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserSignupSerializer(serializers.ModelSerializer):
    """Serializer untuk sign up user"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    email = EmailField(required=True)
    company = serializers.CharField(required=False, default='')
    phone = serializers.CharField(required=False, default='')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name', 'company', 'phone']
    
    def validate_username(self, value):
        """Validate username"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Username harus minimal 3 karakter")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username sudah digunakan")
        return value
    
    def validate_email(self, value):
        """Validate email"""
        value = value.lower()
        
        # Check email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Format email tidak valid")
        
        # Check if email already exists
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email sudah terdaftar")
        
        return value
    
    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise serializers.ValidationError("Password minimal 8 karakter")
        
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("Password harus mengandung minimal 1 huruf besar")
        
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password harus mengandung minimal 1 angka")
        
        return value
    
    def validate(self, data):
        """Validate password match"""
        password = data.get('password')
        password_confirm = data.pop('password_confirm', None)
        
        if password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': 'Password tidak cocok'
            })
        
        return data
    
    def create(self, validated_data):
        """Create user with hashed password"""
        password = validated_data.pop('password')
        company = validated_data.pop('company', '')
        phone = validated_data.pop('phone', '')
        
        user = User.objects.create_user(**validated_data, password=password)
        
        # Create user profile
        UserProfile.objects.create(
            user=user,
            company=company,
            phone=phone
        )
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer untuk login user"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, data):
        """Validate user credentials"""
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Try to find user by username or email
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                # Try by email
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'username': 'Username atau email tidak terdaftar'
                })
        
        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError("User tidak aktif")
        
        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError({
                'password': 'Password salah'
            })
        
        data['user'] = user
        return data


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer untuk refresh token"""
    refresh_token = serializers.CharField(required=True)
    
    def validate_refresh_token(self, value):
        """Validate refresh token"""
        if not value:
            raise serializers.ValidationError("Refresh token diperlukan")
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer untuk update user profile"""
    company = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'company', 'phone']
        read_only_fields = ['email']
    
    def validate_first_name(self, value):
        """Validate first name"""
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Nama depan harus minimal 2 karakter")
        return value
    
    def update(self, instance, validated_data):
        """Update user and profile"""
        company = validated_data.pop('company', None)
        phone = validated_data.pop('phone', None)
        
        # Update User model fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update UserProfile if company or phone provided
        if company is not None or phone is not None:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            if company is not None:
                profile.company = company
            if phone is not None:
                profile.phone = phone
            profile.save()
        
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer untuk change password"""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, required=True, min_length=8)
    
    def validate_new_password(self, value):
        """Validate new password strength"""
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("Password harus mengandung minimal 1 huruf besar")
        
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password harus mengandung minimal 1 angka")
        
        return value
    
    def validate(self, data):
        """Validate passwords match"""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Password tidak cocok'
            })
        
        return data

