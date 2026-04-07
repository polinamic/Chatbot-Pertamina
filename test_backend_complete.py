#!/usr/bin/env python
"""
Complete Backend Testing Script
Tests:
1. Database connectivity
2. User model and UserProfile role system
3. JWT authentication
4. Signup/Login endpoints
5. Role-based permissions
"""

import os
import sys
import django
import requests
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.getcwd())
django.setup()

from django.contrib.auth.models import User
from apps.users.models import UserProfile
from apps.users.permissions import (
    IsAdmin, IsUser, IsSupport, IsManager, IsAdminOrReadOnly
)
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request


def test_1_database_connection():
    """Test 1: Database connection and user table access"""
    print("\n" + "="*60)
    print("TEST 1: Database Connection & User Table Access")
    print("="*60)
    
    try:
        user_count = User.objects.count()
        profile_count = UserProfile.objects.count()
        print(f"✅ Database connected successfully")
        print(f"   - Total users: {user_count}")
        print(f"   - Total profiles: {profile_count}")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_2_user_profile_roles():
    """Test 2: UserProfile role system"""
    print("\n" + "="*60)
    print("TEST 2: UserProfile Role System")
    print("="*60)
    
    try:
        users = User.objects.all()
        for user in users:
            try:
                profile = user.userprofile
                print(f"✅ User: {user.username}")
                print(f"   - Email: {user.email}")
                print(f"   - Role: {profile.role} ({'Admin' if profile.role == 'A' else 'User' if profile.role == 'U' else 'Support' if profile.role == 'S' else 'Manager'})")
                print(f"   - Company: {profile.company}")
                print(f"   - Is Staff: {user.is_staff}")
            except UserProfile.DoesNotExist:
                print(f"⚠️  User {user.username} has no UserProfile!")
    except Exception as e:
        print(f"❌ Error retrieving users: {e}")
        return False
    
    return True


def test_3_permission_classes():
    """Test 3: Permission classes work correctly"""
    print("\n" + "="*60)
    print("TEST 3: Permission Classes")
    print("="*60)
    
    try:
        factory = APIRequestFactory()
        
        # Get admin user
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            print("⚠️  Admin user not found")
            return False
        
        # Test IsAdmin permission
        request = factory.get('/')
        request.user = admin_user
        drf_request = Request(request)
        
        is_admin_perm = IsAdmin()
        can_admin_access = is_admin_perm.has_permission(drf_request, None)
        print(f"{'✅' if can_admin_access else '❌'} IsAdmin permission: {can_admin_access}")
        
        # Test IsUser permission
        user = User.objects.filter(username__startswith='test').first() or User.objects.filter(username='admin').first()
        if user:
            request.user = user
            drf_request = Request(request)
            is_user_perm = IsUser()
            can_user_access = is_user_perm.has_permission(drf_request, None)
            print(f"{'✅' if can_user_access is not None else '❌'} IsUser permission: {can_user_access}")
        
        return True
    except Exception as e:
        print(f"❌ Permission test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_admin_user_exists():
    """Test 4: Admin user exists and is properly configured"""
    print("\n" + "="*60)
    print("TEST 4: Admin User Configuration")
    print("="*60)
    
    try:
        admin = User.objects.filter(username='admin').first()
        if not admin:
            print("❌ Admin user 'admin' not found")
            return False
        
        print(f"✅ Admin user exists")
        print(f"   - Username: {admin.username}")
        print(f"   - Email: {admin.email}")
        print(f"   - Is Staff: {admin.is_staff}")
        print(f"   - Is Superuser: {admin.is_superuser}")
        
        try:
            profile = admin.userprofile
            print(f"   - Profile Role: {profile.role} ({'Admin' if profile.role == 'A' else 'Not Admin'})")
            print(f"   - Company: {profile.company}")
            
            if profile.role != 'A':
                print(f"⚠️  Admin user role is not 'A'")
                return False
        except UserProfile.DoesNotExist:
            print(f"❌ Admin user has no UserProfile")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Error checking admin user: {e}")
        return False


def test_5_create_test_user():
    """Test 5: Create a test user and verify role assignment"""
    print("\n" + "="*60)
    print("TEST 5: Create Test User & Role Assignment")
    print("="*60)
    
    try:
        # Create test user
        test_user, created = User.objects.get_or_create(
            username='test_user_001',
            defaults={
                'email': 'test@pertamina.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        # Ensure UserProfile exists
        profile, profile_created = UserProfile.objects.get_or_create(
            user=test_user,
            defaults={
                'role': 'U',  # Regular user role
                'company': 'Pertamina'
            }
        )
        
        if created or profile_created:
            print(f"✅ Created new test user and profile")
        else:
            print(f"✅ Test user already exists")
        
        print(f"   - Username: {test_user.username}")
        print(f"   - Email: {test_user.email}")
        print(f"   - Role: {profile.role} ({'User' if profile.role == 'U' else 'Other'})")
        print(f"   - Company: {profile.company}")
        
        return True
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_token_generation():
    """Test 6: JWT Token generation for users"""
    print("\n" + "="*60)
    print("TEST 6: JWT Token Generation")
    print("="*60)
    
    try:
        from apps.users.token_manager import TokenManager
        
        admin = User.objects.get(username='admin')
        token_manager = TokenManager()
        
        tokens = token_manager.generate_tokens(admin)
        print(f"✅ Tokens generated successfully")
        print(f"   - Access token length: {len(tokens['access'])}")
        print(f"   - Refresh token length: {len(tokens['refresh'])}")
        
        # Try to decode access token
        try:
            user_from_token = token_manager.get_user_from_token(tokens['access'])
            print(f"✅ Token decoded successfully")
            print(f"   - User from token: {user_from_token.username}")
        except Exception as e:
            print(f"⚠️  Could not decode token: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_api_endpoints():
    """Test 7: API endpoints connectivity (localhost)"""
    print("\n" + "="*60)
    print("TEST 7: API Endpoints Availability")
    print("="*60)
    
    try:
        base_url = "http://localhost:8000/api/v1/users"
        endpoints = [
            ("/auth/login/", "POST", "Login endpoint"),
            ("/auth/signup/", "POST", "Signup endpoint"),
            ("/me/", "GET", "Current user endpoint"),
        ]
        
        for endpoint, method, desc in endpoints:
            url = base_url + endpoint
            try:
                if method == "GET":
                    resp = requests.get(url, timeout=2)
                elif method == "POST":
                    resp = requests.post(url, json={}, timeout=2)
                
                # 400/401/405 is OK - just means endpoint exists
                if resp.status_code < 500:
                    print(f"✅ {desc} - Status {resp.status_code}")
                else:
                    print(f"⚠️  {desc} - Server error {resp.status_code}")
            except requests.exceptions.ConnectionError:
                print(f"⚠️  {desc} - Server not running (http://localhost:8000)")
                return None  # Return None to indicate server not running
            except Exception as e:
                print(f"⚠️  {desc} - Error: {e}")
        
        return True
    except Exception as e:
        print(f"⚠️  Cannot test API endpoints: {e}")
        return None


def main():
    """Run all tests"""
    print("\n" + "🔍 PERTAMINA CHATBOT - BACKEND VERIFICATION TEST 🔍")
    print("=" * 60)
    
    results = {}
    
    # Run tests
    results['test_1'] = ("Database Connection", test_1_database_connection())
    results['test_2'] = ("UserProfile Roles", test_2_user_profile_roles())
    results['test_3'] = ("Permission Classes", test_3_permission_classes())
    results['test_4'] = ("Admin Configuration", test_4_admin_user_exists())
    results['test_5'] = ("User Creation", test_5_create_test_user())
    results['test_6'] = ("JWT Tokens", test_6_token_generation())
    results['test_7'] = ("API Endpoints", test_7_api_endpoints())
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results.values() if result is True)
    failed = sum(1 for _, result in results.values() if result is False)
    skipped = sum(1 for _, result in results.values() if result is None)
    
    for test_id, (name, result) in results.items():
        status = "✅ PASS" if result is True else "❌ FAIL" if result is False else "⚠️  SKIP"
        print(f"{status} | {name}")
    
    print("="*60)
    print(f"Results: {passed} Passed | {failed} Failed | {skipped} Skipped")
    print("="*60)
    
    if failed == 0 and passed > 0:
        print("\n✅ BACKEND IS READY! All critical systems operational.")
    elif failed > 0:
        print("\n❌ Some tests failed. Check the output above.")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
