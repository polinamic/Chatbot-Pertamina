#!/usr/bin/env python
"""Simple test for signup form"""

import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable TF warnings

import django
from django.conf import settings

# Add testserver to ALLOWED_HOSTS
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

django.setup()

from django.test import Client
from django.contrib.auth.models import User
import sys

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

print("Testing Signup Form...")
print("-" * 50)

# Clean up test user
User.objects.filter(username='testuser999').delete()

# Create client
client = Client()

#Test: POST valid signup
print("\nTest 1: POST valid signup data")
response = client.post('/auth/signup/', {
    'username': 'testuser999',
    'email': 'testuser999@example.com',
    'password': 'TestPass123',
})

print(f"Response Status: {response.status_code}")
if response.status_code == 302:
    print("✓ Redirect successful (signup worked!)")
    user = User.objects.filter(username='testuser999').first()
    if user:
        print(f"✓ User created: {user.username}")
else:
    print(f"Response status: {response.status_code}")
    # Extract error messages from response
    if b'Terjadi Kesalahan' in response.content:
        print("✗ Form has error!")
        # Try to extract error message
        content_str = response.content.decode('utf-8', errors='ignore')
        if 'Terjadi Kesalahan' in content_str:
            idx = content_str.find('Terjadi Kesalahan')
            print("Error section:", content_str[idx:idx+500])
    elif response.status_code == 200:
        print("✓ Form returned (might have validation errors)")
        # Check if user was created anyway
        user = User.objects.filter(username='testuser999').first()
        if user:
            print(f"✓ User WAS created: {user.username}")
        else:
            print("✗ User was NOT created")


print("\n" + "-" * 50)
print("Test Complete")

# Cleanup
User.objects.filter(username='testuser999').delete()
