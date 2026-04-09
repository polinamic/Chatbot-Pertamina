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
print("RESPONSE CAPTURE TEST")
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

print(f"Response Status: {resp.status_code}")
print(f"Response Content-Type: {resp.get('Content-Type', 'unknown')}")

# Save full response to file
with open('response_dump.html', 'w', encoding='utf-8') as f:
    f.write(resp.content.decode('utf-8', errors='ignore'))

print(f"\nFull response saved to response_dump.html")

# Show key parts
content_str = resp.content.decode('utf-8', errors='ignore')
print(f"\n[First 500 chars of response]")
print(content_str[:500])

# Check if this is signup.html template
if 'signup-form' in content_str:
    print("\n[FOUND] This is signup.html template (contains 'signup-form')")
elif 'signup_form' in content_str:
    print("\n[FOUND] This is signup form (contains 'signup_form')")
else:
    print("\n[NOT FOUND] This doesn't look like signup template")

# Check for form method
if 'method="POST"' in content_str or "method='POST'" in content_str:
    print("[FOUND] Form uses POST method")

# Check for JavaScript includes
if 'validate' in content_str or 'validation' in content_str:
    print("[FOUND] Contains validation code")

print("\n" + "="*60 + "\n")

# Clean
User.objects.filter(username='signup_test').delete()
