#!/usr/bin/env python
"""
Script untuk membuat admin user dengan credentials yang sudah ditentukan
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.users.models import UserProfile

# Credentials yang akan dibuat
ADMIN_CREDENTIALS = {
    'username': 'admin',
    'email': 'admin@pertamina.com',
    'password': 'Admin@12345',
    'first_name': 'Admin',
    'last_name': 'User'
}

print('\n' + '='*60)
print('🔑 CREATING ADMIN USER')
print('='*60)

try:
    # Check if user already exists
    if User.objects.filter(username=ADMIN_CREDENTIALS['username']).exists():
        print(f"\n⚠️  User '{ADMIN_CREDENTIALS['username']}' sudah ada di database")
        existing_user = User.objects.get(username=ADMIN_CREDENTIALS['username'])
        print(f"ID: {existing_user.id}")
        print(f"Email: {existing_user.email}")
        
        # Check profile
        try:
            profile = existing_user.profile
            print(f"Role: {profile.get_role_display()}")
            print(f"Verified: {profile.is_verified}")
        except:
            print("Profile: Tidak ditemukan")
        
        print("\n✅ Admin user sudah siap digunakan!")
        sys.exit(0)
    
    # Create user
    print(f"\n📝 Creating user: {ADMIN_CREDENTIALS['username']}")
    
    user = User.objects.create_user(
        username=ADMIN_CREDENTIALS['username'],
        email=ADMIN_CREDENTIALS['email'],
        password=ADMIN_CREDENTIALS['password'],
        first_name=ADMIN_CREDENTIALS['first_name'],
        last_name=ADMIN_CREDENTIALS['last_name'],
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
    
    # Print success
    print('\n' + '='*60)
    print('✅ ADMIN USER BERHASIL DIBUAT!')
    print('='*60)
    print(f'\nUsername  : {ADMIN_CREDENTIALS["username"]}')
    print(f'Email     : {ADMIN_CREDENTIALS["email"]}')
    print(f'Password  : {ADMIN_CREDENTIALS["password"]}')
    print(f'Full Name : {ADMIN_CREDENTIALS["first_name"]} {ADMIN_CREDENTIALS["last_name"]}')
    print(f'Role      : Admin')
    print(f'Staff     : Yes')
    print(f'Verified  : Yes')
    
    print('\n' + '='*60)
    print('🔐 CREDENTIALS TERSIMPAN DI:')
    print('   ADMIN_CREDENTIALS.txt')
    print('='*60)
    
    print('\n✨ Silakan login dengan credentials di atas!')
    print('   URL: http://localhost:8000/auth/login/\n')
    
except Exception as e:
    print(f'\n❌ Error: {str(e)}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
