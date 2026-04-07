#!/usr/bin/env python
"""
Backend Fix Script
Ensures all users have UserProfile records with proper roles
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.getcwd())
django.setup()

from django.contrib.auth.models import User
from apps.users.models import UserProfile


def fix_missing_profiles():
    """Create UserProfile for all users that don't have one"""
    print("\n" + "="*60)
    print("FIXING: Create Missing UserProfiles")
    print("="*60)
    
    users = User.objects.all()
    created_count = 0
    
    for user in users:
        # Check if profile exists using filter instead of attribute access
        profile = UserProfile.objects.filter(user=user).first()
        
        if profile:
            print(f"OK User '{user.username}' already has profile (role={profile.role})")
        else:
            # Determine role: admin/staff get 'A', others get 'U'
            if user.is_superuser or user.is_staff:
                role = 'A'
            else:
                role = 'U'
            
            profile = UserProfile.objects.create(
                user=user,
                role=role,
                company='Pertamina'
            )
            created_count += 1
            print(f"OK Created profile for '{user.username}' with role '{role}'")
    
    print(f"\nOK Total profiles created: {created_count}")
    return True


def verify_backend():
    """Verify all backend systems"""
    print("\n" + "="*60)
    print("VERIFYING: Backend Systems")
    print("="*60)
    
    # 1. Database access
    print("\n[1] Database Connection:")
    try:
        user_count = User.objects.count()
        profile_count = UserProfile.objects.count()
        print(f"    OK Users: {user_count}")
        print(f"    OK Profiles: {profile_count}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False
    
    # 2. Users and Roles
    print("\n[2] User Roles:")
    try:
        for user in User.objects.all()[:5]:  # Show first 5
            profile = UserProfile.objects.get(user=user)
            role_name = 'Admin' if profile.role == 'A' else 'User' if profile.role == 'U' else 'Support' if profile.role == 'S' else 'Manager'
            print(f"    OK {user.username:15} - Role: {profile.role} ({role_name})")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False
    
    # 3. Admin user
    print("\n[3] Admin User:")
    try:
        admin = User.objects.get(username='admin')
        profile = UserProfile.objects.get(user=admin)
        print(f"    OK Username: admin")
        print(f"    OK Email: {admin.email}")
        print(f"    OK Role: {profile.role} ({'Admin' if profile.role == 'A' else 'Not Admin!'})")
        print(f"    OK Is Superuser: {admin.is_superuser}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False
    
    # 4. JWT Tokens
    print("\n[4] JWT Token Generation:")
    try:
        from apps.users.token_manager import TokenManager
        
        admin = User.objects.get(username='admin')
        tokens = TokenManager.generate_tokens(admin.id, admin.email)
        print(f"    OK Access token generated (length: {len(tokens['access_token'])})")
        print(f"    OK Refresh token generated (length: {len(tokens['refresh_token'])})")
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. Permission classes
    print("\n[5] Permission Classes:")
    try:
        from apps.users.permissions import IsAdmin, IsUser
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request
        
        factory = APIRequestFactory()
        admin = User.objects.get(username='admin')
        
        request = factory.get('/')
        request.user = admin
        drf_request = Request(request)
        
        is_admin = IsAdmin()
        result = is_admin.has_permission(drf_request, None)
        print(f"    OK IsAdmin check: {result}")
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    print("\n--- BACKEND FIX & VERIFICATION SCRIPT ---")
    
    # Fix missing profiles
    if not fix_missing_profiles():
        print("ERROR: Fix failed!")
        return 1
    
    # Verify backend
    if not verify_backend():
        print("ERROR: Verification failed!")
        return 1
    
    print("\n" + "="*60)
    print("SUCCESS: BACKEND IS READY!")
    print("="*60)
    print("\nNext steps:")
    print("1. Run: python manage.py runserver")
    print("2. Test signup/login endpoints")
    print("3. Verify role-based routing in frontend")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
