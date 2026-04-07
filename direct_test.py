import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
django.setup()

from django.contrib.auth.models import User
from django.test import Client

print("\n" + "="*60)
print("DIRECT SIGNUP TEST")
print("="*60 + "\n")

# Clean
User.objects.filter(username='signup_test').delete()

# Test form POST
client = Client()
resp = client.post('/auth/signup/', {
    'username': 'signup_test',
    'email': 'signuptest@test.com',
    'password': 'SignupTest123',
})

print(f"POST Response Status: {resp.status_code}")
if resp.status_code == 302:
    print("[SUCCESS] Redirected (signup likely succeeded)")
else:
    print(f"[ERROR] Status {resp.status_code} (not a redirect)")
    # Parse error from response
    if b'Terjadi Kesalahan' in resp.content:
        print("\n[ERROR MESSAGE FROM FORM]")
        content_str = resp.content.decode('utf-8', errors='ignore')
        start = content_str.find('Terjadi Kesalahan')
        if start > 0:
            print(content_str[start:start+300])

# Check DB
user = User.objects.filter(username='signup_test').first()
if user:
    print(f"[SUCCESS] User in database: {user.username} ({user.email})")
else:
    print("[ERROR] User NOT in database")

#Clean
User.objects.filter(username='signup_test').delete()
print("\n" + "="*60 + "\n")

