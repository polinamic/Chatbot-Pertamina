#!/usr/bin/env python
"""
Test script untuk authentication backend
Usage: python test_auth_backend.py
"""

import os
import sys
import django
import json
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from apps.users.models import UserProfile


class AuthBackendTester:
    """Tester untuk Auth Backend"""
    
    def __init__(self):
        self.client = Client()
        self.test_data = {
            'username': f'testuser_{datetime.now().timestamp()}',
            'email': f'test{datetime.now().timestamp()}@pertamina.com',
            'password': 'TestPassword123',
            'password_confirm': 'TestPassword123',
            'first_name': 'Test',
            'last_name': 'User',
            'company': 'Pertamina'
        }
        self.access_token = None
        self.refresh_token = None
        
    def print_header(self, text):
        """Print section header"""
        print(f'\n{"="*60}')
        print(f'🧪 {text}')
        print(f'{"="*60}')
    
    def print_success(self, text):
        """Print success message"""
        print(f'✅ {text}')
    
    def print_error(self, text):
        """Print error message"""
        print(f'❌ {text}')
    
    def print_info(self, text):
        """Print info message"""
        print(f'ℹ️  {text}')
    
    def test_signup(self):
        """Test signup endpoint"""
        self.print_header('TEST SIGNUP - Membuat user baru')
        
        print(f'Data signup:')
        for key, value in self.test_data.items():
            if key != 'password' and key != 'password_confirm':
                print(f'  {key}: {value}')
        
        response = self.client.post(
            '/api/users/auth/signup/',
            data=json.dumps(self.test_data),
            content_type='application/json'
        )
        
        if response.status_code == 201:
            data = response.json()
            self.print_success(f"Signup berhasil! Status code: {response.status_code}")
            self.print_info(f"User ID: {data['user']['id']}")
            self.print_info(f"Username: {data['user']['username']}")
            self.print_info(f"Email: {data['user']['email']}")
            
            # Store tokens
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            
            if self.access_token:
                self.print_info(f"Access token received: {self.access_token[:50]}...")
            
            return True
        else:
            self.print_error(f"Signup gagal! Status code: {response.status_code}")
            self.print_error(f"Response: {response.json()}")
            return False
    
    def test_login(self):
        """Test login endpoint"""
        self.print_header('TEST LOGIN - Login dengan user')
        
        login_data = {
            'username': self.test_data['username'],
            'password': self.test_data['password']
        }
        
        print(f'Login dengan:')
        print(f'  username: {login_data["username"]}')
        print(f'  password: (hidden)')
        
        response = self.client.post(
            '/api/users/auth/login/',
            data=json.dumps(login_data),
            content_type='application/json'
        )
        
        if response.status_code == 200:
            data = response.json()
            self.print_success(f"Login berhasil! Status code: {response.status_code}")
            self.print_info(f"User: {data['user']['email']}")
            
            # Update tokens
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            
            return True
        else:
            self.print_error(f"Login gagal! Status code: {response.status_code}")
            self.print_error(f"Response: {response.json()}")
            return False
    
    def test_get_current_user(self):
        """Test get current user endpoint"""
        self.print_header('TEST GET CURRENT USER')
        
        if not self.access_token:
            self.print_error("Tidak ada access token")
            return False
        
        response = self.client.get(
            '/api/users/me/',
            HTTP_AUTHORIZATION=f'Bearer {self.access_token}'
        )
        
        if response.status_code == 200:
            data = response.json()
            self.print_success(f"Get current user berhasil! Status code: {response.status_code}")
            self.print_info(f"Username: {data['username']}")
            self.print_info(f"Email: {data['email']}")
            self.print_info(f"Full Name: {data['first_name']} {data['last_name']}")
            
            if 'profile' in data:
                profile = data['profile']
                self.print_info(f"Role: {profile.get('role', 'N/A')}")
                self.print_info(f"Company: {profile.get('company', 'N/A')}")
            
            return True
        else:
            self.print_error(f"Get current user gagal! Status code: {response.status_code}")
            self.print_error(f"Response: {response.json()}")
            return False
    
    def test_update_profile(self):
        """Test update profile endpoint"""
        self.print_header('TEST UPDATE PROFILE')
        
        if not self.access_token:
            self.print_error("Tidak ada access token")
            return False
        
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '081234567890'
        }
        
        print(f'Data update:')
        for key, value in update_data.items():
            print(f'  {key}: {value}')
        
        response = self.client.put(
            '/api/users/update_profile/',
            data=json.dumps(update_data),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.access_token}'
        )
        
        if response.status_code == 200:
            data = response.json()
            self.print_success(f"Update profile berhasil! Status code: {response.status_code}")
            self.print_info(f"Full Name: {data['first_name']} {data['last_name']}")
            return True
        else:
            self.print_error(f"Update profile gagal! Status code: {response.status_code}")
            self.print_error(f"Response: {response.json()}")
            return False
    
    def test_logout(self):
        """Test logout endpoint"""
        self.print_header('TEST LOGOUT')
        
        if not self.access_token:
            self.print_error("Tidak ada access token")
            return False
        
        response = self.client.post(
            '/api/users/auth/logout/',
            HTTP_AUTHORIZATION=f'Bearer {self.access_token}'
        )
        
        if response.status_code == 200:
            self.print_success(f"Logout berhasil! Status code: {response.status_code}")
            return True
        else:
            self.print_error(f"Logout gagal! Status code: {response.status_code}")
            self.print_error(f"Response: {response.json()}")
            return False
    
    def test_invalid_login(self):
        """Test invalid login"""
        self.print_header('TEST INVALID LOGIN - Password salah')
        
        login_data = {
            'username': self.test_data['username'],
            'password': 'WrongPassword123'
        }
        
        response = self.client.post(
            '/api/users/auth/login/',
            data=json.dumps(login_data),
            content_type='application/json'
        )
        
        if response.status_code != 200:
            self.print_success(f"Rejected dengan benar! Status code: {response.status_code}")
            return True
        else:
            self.print_error(f"Validation failed! Invalid password was accepted")
            return False
    
    def test_duplicate_username(self):
        """Test duplicate username"""
        self.print_header('TEST DUPLICATE USERNAME')
        
        duplicate_data = self.test_data.copy()
        duplicate_data['email'] = f'different{datetime.now().timestamp()}@pertamina.com'
        
        response = self.client.post(
            '/api/users/auth/signup/',
            data=json.dumps(duplicate_data),
            content_type='application/json'
        )
        
        if response.status_code != 201:
            self.print_success(f"Rejected dengan benar! Status code: {response.status_code}")
            return True
        else:
            self.print_error(f"Validation failed! Duplicate username was accepted")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print('\n╔════════════════════════════════════════════════════════════╗')
        print('║         🔐 AUTH BACKEND TEST SUITE                         ║')
        print('╚════════════════════════════════════════════════════════════╝')
        
        results = {
            'Test Signup': self.test_signup(),
            'Test Login': self.test_login(),
            'Test Get Current User': self.test_get_current_user(),
            'Test Update Profile': self.test_update_profile(),
            'Test Invalid Login': self.test_invalid_login(),
            'Test Duplicate Username': self.test_duplicate_username(),
            'Test Logout': self.test_logout(),
        }
        
        # Summary
        self.print_header('TEST SUMMARY')
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = '✅ PASS' if result else '❌ FAIL'
            print(f'{status} - {test_name}')
        
        print(f'\n{"="*60}')
        print(f'📊 TOTAL: {passed}/{total} tests passed')
        print(f'{"="*60}\n')
        
        return passed == total


if __name__ == '__main__':
    try:
        tester = AuthBackendTester()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print('\n\n⚠️  Test dibatalkan')
        sys.exit(0)
    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
