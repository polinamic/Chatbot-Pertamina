#!/usr/bin/env python
"""
Script standalone untuk membuat admin user
Usage: python create_admin_user.py
"""

import os
import sys
import django
import getpass

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import IntegrityError
from apps.users.models import UserProfile


def validate_password(password):
    """Validate password strength"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password minimal 8 karakter")
    
    if not any(char.isupper() for char in password):
        errors.append("Password harus mengandung minimal 1 huruf besar")
    
    if not any(char.isdigit() for char in password):
        errors.append("Password harus mengandung minimal 1 angka")
    
    return errors


def get_username():
    """Get and validate username"""
    while True:
        username = input('\n📝 Masukkan username: ').strip()
        
        if not username:
            print('❌ Username tidak boleh kosong')
            continue
        
        if len(username) < 3:
            print('❌ Username minimal 3 karakter')
            continue
        
        if User.objects.filter(username=username).exists():
            print('❌ Username sudah digunakan')
            continue
        
        return username


def get_email():
    """Get and validate email"""
    while True:
        email = input('📝 Masukkan email: ').strip().lower()
        
        if not email:
            print('❌ Email tidak boleh kosong')
            continue
        
        if '@' not in email or '.' not in email:
            print('❌ Format email tidak valid')
            continue
        
        if User.objects.filter(email=email).exists():
            print('❌ Email sudah terdaftar')
            continue
        
        return email


def get_password():
    """Get and validate password"""
    while True:
        print('\n🔐 Password requirements:')
        print('   - Minimal 8 karakter')
        print('   - Minimal 1 huruf besar')
        print('   - Minimal 1 angka')
        
        password = getpass.getpass('Masukkan password: ')
        
        if not password:
            print('❌ Password tidak boleh kosong')
            continue
        
        # Validate password
        errors = validate_password(password)
        if errors:
            for error in errors:
                print(f'❌ {error}')
            continue
        
        # Confirm password
        password_confirm = getpass.getpass('Konfirmasi password: ')
        if password != password_confirm:
            print('❌ Password tidak cocok')
            continue
        
        return password


def create_admin():
    """Create admin user"""
    print('\n' + '='*50)
    print('🔑 CREATE ADMIN USER - Chatbot Pertamina')
    print('='*50)
    
    try:
        # Get input
        username = get_username()
        email = get_email()
        password = get_password()
        
        first_name = input('\n📝 Masukkan first name (default: Admin): ').strip() or 'Admin'
        last_name = input('📝 Masukkan last name (default: User): ').strip() or 'User'
        
        # Create user
        print('\n⏳ Membuat admin user...')
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=True,
        )
        
        # Create profile
        profile = UserProfile.objects.create(
            user=user,
            role='A',  # Admin
            company='Pertamina',
            is_verified=True
        )
        
        # Success message
        print('\n' + '='*50)
        print('✅ ADMIN USER BERHASIL DIBUAT!')
        print('='*50)
        print(f'Username  : {username}')
        print(f'Email     : {email}')
        print(f'Full Name : {first_name} {last_name}')
        print(f'Role      : Admin')
        print('='*50)
        print('⚠️  Jangan bagikan credentials ini!')
        print('='*50 + '\n')
        
        return True
        
    except IntegrityError as e:
        print(f'\n❌ Gagal membuat admin user: {str(e)}')
        return False
    except Exception as e:
        print(f'\n❌ Terjadi error: {str(e)}')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        create_admin()
    except KeyboardInterrupt:
        print('\n\n⚠️  Operasi dibatalkan')
        sys.exit(0)
    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        sys.exit(1)
