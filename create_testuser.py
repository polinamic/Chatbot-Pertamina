#!/usr/bin/env python
"""Script to create test user account"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.users.models import UserProfile

# Create test user
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={
        'email': 'test@pertamina.com',
        'first_name': 'Test',
        'last_name': 'User',
        'is_staff': False,
        'is_superuser': False
    }
)

if created:
    user.set_password('Test@1234')
    user.save()
    
    # Create profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = 'U'
    profile.department = 'IT'
    profile.company = 'PT Pertamina'
    profile.phone = '021-XXXX-XXXX'
    profile.save()
    
    print('✓ Akun berhasil dibuat!')
    print(f'  Username: testuser')
    print(f'  Email: test@pertamina.com')
    print(f'  Password: Test@1234')
else:
    print('✗ Akun testuser sudah ada')
    print(f'  Email: {user.email}')
