import os
import sys
import io

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
    
# Capture stdout/stderr
captured_output = io.StringIO()
sys.stdout = captured_output
sys.stderr = captured_output

django.setup()

# Restore stdout
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

from django.contrib.auth.models import User
from django.test import Client

print("\n" + "="*60)
print("DIRECT SIGNUP TEST V2")
print("="*60 + "\n")

# Clean
User.objects.filter(username='signup_test').delete()

# Test form POST to /auth/signup/ (form-based view path)
print("[TEST 1] POST to /auth/signup/ (form-based view)")
client = Client()
sys.stdout.flush()

resp = client.post('/auth/signup/', {
    'username': 'signup_test',
    'email': 'signuptest@test.com',
    'password': 'SignupTest123',
})

# Show captured output from Django request
captured = captured_output.getvalue()
if captured:
    print("=== CAPTURED STDOUT/STDERR FROM REQUEST ===")
    print(captured)
    print("=== END CAPTURED OUTPUT ===\n")

print(f"POST Response Status: {resp.status_code}")
print(f"Response URL: {resp.request.get('PATH_INFO', 'unknown')}")

if resp.status_code == 302:
    print("[SUCCESS] Redirected (signup likely succeeded)")
    print(f"Redirect to: {resp.url}")
else:
    print(f"[ERROR] Status {resp.status_code} (not a redirect)")
    # Parse error from response
    if b'Terjadi Kesalahan' in resp.content:
        print("\n[ERROR MESSAGE FROM FORM]")
        content_str = resp.content.decode('utf-8', errors='ignore')
        start = content_str.find('Terjadi Kesalahan')
        if start > 0:
            print(content_str[start:start+400])

# Check DB
user = User.objects.filter(username='signup_test').first()
if user:
    print(f"[SUCCESS] User in database: {user.username} ({user.email})")
else:
    print("[ERROR] User NOT in database")

# Clean
User.objects.filter(username='signup_test').delete()

print("\n" + "="*60)
print("\n[TEST 2] Testing URL resolution manually")

from django.urls import resolve
try:
    match = resolve('/auth/signup/')
    print(f"URL /auth/signup/ resolves to: {match.func.__module__}.{match.func.__name__ if hasattr(match.func, '__name__') else 'ViewClass'}")
    print(f"URL name: {match.url_name}")
except Exception as e:
    print(f"ERROR resolving /auth/signup/: {e}")

print("\n" + "="*60 + "\n")
