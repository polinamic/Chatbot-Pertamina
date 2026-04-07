import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from django.urls import resolve, get_resolver

print("\n" + "="*70)
print("COMPREHENSIVE URL & ROUTING DEBUG")
print("="*70 + "\n")

# Test 1: Resolve the path
print("[TEST 1] URL Resolution")
try:
    match = resolve('/auth/signup/')
    print(f"OK - /auth/signup/ resolves to: {match.func}")
    print(f"  Function: {match.func.__module__}.{match.func.__name__ if hasattr(match.func, '__name__') else match.func.__class__.__name__}")
    print(f"  URL name: {match.url_name}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n[TEST 2] Check if /auth/signup/ appears in urlpatterns")
resolver = get_resolver()
for pattern in resolver.url_patterns:
    pattern_str = str(pattern.pattern)
    if 'auth' in pattern_str or 'signup' in pattern_str:
        print(f"  Found pattern: {pattern_str} -> {pattern.callback if hasattr(pattern, 'callback') else 'URLconf'}")

print("\n[TEST 3] POST request and inspect response")
client = Client()
User.objects.filter(username='test_debug').delete()

resp = client.post('/auth/signup/', {
    'username': 'test_debug',
    'email': 'test@test.com',
    'password': 'Test1234',
})

print(f"Response Status: {resp.status_code}")
print(f"Response Headers: {dict(resp.items())}")
print(f"Response Content-Type: {resp.get('Content-Type')}")

#Check response content
content = resp.content.decode('utf-8', errors='ignore')
if "!!!VIEW WAS CALLED!!!" in content:
    print("[SUCCESS] VIEW WAS CALLED (found custom text)")
elif "signup-form" in content:
    print("[FAIL] Response contains signup.html template (view not called, form rendered)")
else:
    print("[UNKNOWN] Unknown response type")

print(f"\nFirst 300 chars of response:\n{content[:300]}")

print("\n" + "="*70 + "\n")

User.objects.filter(username='test_debug').delete()
