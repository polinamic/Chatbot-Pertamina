import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
django.setup()

from django.contrib.auth.models import User
from django.urls import resolve
from django.test import RequestFactory

print("\n" + "="*70)
print("DIRECT VIEW CALL TEST")
print("="*70 + "\n")

# Clean
User.objects.filter(username='test_direct').delete()

# Get the view function
resolver_match = resolve('/auth/signup/')
view_func = resolver_match.func

print(f"[URL Resolution]")
print(f"URL: /auth/signup/")
print(f"Resolves to: {view_func.__module__}.{view_func.__name__}")

# Create a POST request manually
factory = RequestFactory()
request = factory.post('/auth/signup/', {
    'username': 'test_direct',
    'email': 'test@test.com',
    'password': 'Test1234',
})

print(f"\n[Calling view function directly]")
print(f"Function: {view_func}")

try:
    response = view_func(request)
    print(f"[Response returned]")
    print(f"Status: {response.status_code if hasattr(response, 'status_code') else 'no status'}")
    print(f"Type: {type(response)}")
    
    if hasattr(response, 'content'):
        content = response.content.decode('utf-8', errors='ignore')
        if 'Password tidak cocok' in content:
            print("[FOUND] 'Password tidak cocok' in response")
        if 'signup-form' in content:
            print("[FOUND] 'signup-form' in response")
        print(f"[Content preview] {content[:200]}")
        
except Exception as e:
    print(f"[EXCEPTION] {type(e).__name__}: {e}")
    import traceback
    print(traceback.format_exc())

# Check if debug file was created
import os
if os.path.exists('signup_view_called.txt'):
    print("\n[DEBUG FILE] signup_view_called.txt was created!")
    with open('signup_view_called.txt', 'r') as f:
        print(f.read())
else:
    print("\n[NO DEBUG FILE] View never called")

# Check database
user = User.objects.filter(username='test_direct').first()
if user:
    print(f"\n[DB] User was created: {user.username}")
else:
    print(f"\n[DB] User was not created")

print("\n" + "="*70 + "\n")

# Clean
User.objects.filter(username='test_direct').delete()
