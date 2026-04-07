#!/usr/bin/env python
"""Test signup flow to debug POST issue"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))

# Add testserver to ALLOWED_HOSTS before Django imports
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Test data
test_username = 'testuser123'
test_email = 'test@example.com'
test_password = 'TestPassword123'

# Clean up any existing test user
User.objects.filter(username=test_username).delete()

print("=" * 60)
print("TESTING SIGNUP FLOW")
print("=" * 60)
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}\n")

# Test 1: GET request
print("[TEST 1] GET /auth/signup/")
client = Client()
response = client.get('/auth/signup/')
print(f"Status Code: {response.status_code}")
print(f"Content Length: {len(response.content)} bytes")
assert response.status_code == 200, "GET signup page failed"
print("✓ GET signup page works")

# Test 2: POST with valid data
print("\n[TEST 2] POST /auth/signup/ with valid data")
data = {
    'username': test_username,
    'email': test_email,
    'password': test_password,
}
response = client.post('/auth/signup/', data)
print(f"Status Code: {response.status_code}")
print(f"Redirect URL: {response.get('location', 'No redirect')}")

if response.status_code == 302:
    print("✓ POST signup returns redirect (success)")
    # Check if user was created
    user = User.objects.filter(username=test_username).first()
    if user:
        print(f"✓ User created: {user.username} ({user.email})")
    else:
        print("✗ User NOT created in database")
elif response.status_code == 200:
    print("✓ POST signup returns 200 (form with validation errors)")
else:
    print(f"✗ POST signup returned {response.status_code}, expected 302 or 200")

# Test 3: POST with duplicate username
print("\n[TEST 3] POST /auth/signup/ with duplicate username")
data2 = {
    'username': test_username,
    'email': 'another@example.com',
    'password': 'AnotherPass123',
}
response = client.post('/auth/signup/', data2)
print(f"Status Code: {response.status_code}")
if response.status_code == 200 and b'Username sudah digunakan' in response.content:
    print("✓ Duplicate username validation works")
else:
    print(f"✗ Expected validation error for duplicate username")

# Test 4: POST with invalid password
print("\n[TEST 4] POST /auth/signup/ with invalid password")
User.objects.filter(username='newuser123').delete()
data3 = {
    'username': 'newuser123',
    'email': 'newuser@example.com',
    'password': 'weakpass',  # No uppercase or number
}
response = client.post('/auth/signup/', data3)
print(f"Status Code: {response.status_code}")
if response.status_code == 200 and (b'minimal 8' in response.content or b'huruf besar' in response.content or b'Password' in response.content):
    print("✓ Password validation works")
else:
    print(f"✗ Expected password validation error")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

# Clean up
User.objects.filter(username=test_username).delete()
User.objects.filter(username='newuser123').delete()

