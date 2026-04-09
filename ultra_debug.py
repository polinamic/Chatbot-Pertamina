import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
django.setup()

from django.contrib.auth.models import User
from django.test import Client

print("\n" + "="*70)
print("ULTRA DEBUG TEST")
print("="*70 + "\n")

# Clean
User.objects.filter(username='test_ultra').delete()

# Test: Make a custom request object and trace it through middleware
print("[TEST] Creating manual request")
request_factory_path = '/auth/signup/'
client = Client()

# Add custom attribute to trace
print(f"\n[Request] Posting to: {request_factory_path}")
print("[Request] Data: username=test_ultra, email=test@test.com,password=Test1234")

resp = client.post(request_factory_path, {
    'username': 'test_ultra',
    'email': 'test@test.com',
    'password': 'Test1234',
})

print(f"\n[Response] Status: {resp.status_code}")
print(f"[Response] Headers: Content-Type={resp.get('Content-Type')}")

# Check file
import os
if os.path.exists('signup_view_called.txt'):
    print("\n[SUCCESS] signup_view_called.txt EXISTS")
    with open('signup_view_called.txt', 'r') as f:
        print(f.read())
else:
    print("\n[FAILURE] signup_view_called.txt does NOT exist")

# Check database
user = User.objects.filter(username='test_ultra').first()
if user:
    print(f"\n[DB] User exists: {user.username} ({user.email})")
else:
    print(f"\n[DB] User does NOT exist")

# Check response content
content = resp.content.decode('utf-8', errors='ignore')
if 'Password tidak cocok' in content:
    print("\n[RESPONSE] Contains error: 'Password tidak cocok'")
    # Find the error
    idx = content.find('Password tidak cocok')
    print(f"Context: ...{content[max(0,idx-100):idx+100]}...")

print("\n" + "="*70 + "\n")

# Clean
User.objects.filter(username='test_ultra').delete()
