#!/usr/bin/env python
"""
Detailed upload test to debug any issues
"""
import requests
import json

BASE_URL = 'http://127.0.0.1:8000'
EMAIL = 'admin@pertamina.com'
PASSWORD = 'admin123456'
TEST_FILE = 'test_upload.txt'

print("\n" + "="*70)
print("DETAILED UPLOAD TEST WITH DEBUGGING")
print("="*70)

# Create session
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# Step 1: Get CSRF token
print("\n[STEP 1] Getting CSRF token from login page...")
try:
    login_page = session.get(f'{BASE_URL}/auth/login/')
    print(f"  Status: {login_page.status_code}")
    print(f"  Cookies before login: {list(session.cookies.keys())}")
    
    csrf_token = session.cookies.get('csrftoken')
    print(f"  ✓ CSRF token from cookie: {csrf_token[:20] if csrf_token else 'NOT FOUND'}...")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Step 2: Login
print("\n[STEP 2] Logging in...")
login_data = {
    'email': EMAIL,
    'password': PASSWORD,
    'csrfmiddlewaretoken': csrf_token  # IMPORTANT: Add CSRF token to POST data
}

try:
    print(f"  POST data keys: {list(login_data.keys())}")
    response = session.post(f'{BASE_URL}/auth/login/', data=login_data, allow_redirects=False)
    print(f"  Status: {response.status_code}")
    print(f"  Headers: Location={response.headers.get('Location', 'N/A')}")
    
    if response.status_code == 302:
        # Follow redirect
        redirect_url = response.headers.get('Location')
        if redirect_url.startswith('/'):
            redirect_url = BASE_URL + redirect_url
        follow = session.get(redirect_url, allow_redirects=True)
        print(f"  ✓ Followed redirect, status: {follow.status_code}")
    
    print(f"  Cookies after login: {list(session.cookies.keys())}")
    if 'sessionid' in session.cookies:
        print(f"  ✓ Session ID: {session.cookies['sessionid'][:20]}...")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Step 3: Upload file
print("\n[STEP 3] Uploading file...")
print(f"  File: {TEST_FILE}")

try:
    import os
    if not os.path.exists(TEST_FILE):
        print(f"  ✗ File not found!")
    else:
        file_size = os.path.getsize(TEST_FILE)
        print(f"  File size: {file_size} bytes")
        
        with open(TEST_FILE, 'rb') as f:
            files = {'file': (TEST_FILE, f, 'text/plain')}
            headers = {
                'X-CSRFToken': session.cookies.get('csrftoken', '')
            }
            
            print(f"  Sending POST to /dashboard/api/documents/upload/")
            print(f"  Headers: {headers}")
            print(f"  CSRF token in header: {headers['X-CSRFToken'][:20] if headers['X-CSRFToken'] else 'NOT SET'}...")
            
            response = session.post(
                f'{BASE_URL}/dashboard/api/documents/upload/',
                files=files,
                headers=headers,
                timeout=30
            )
            
            print(f"\n  Response Status: {response.status_code}")
            print(f"  Response Headers: Content-Type={response.headers.get('Content-Type')}")
            print(f"  Response Length: {len(response.text)} bytes")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"\n  ✓ SUCCESS RESPONSE:")
                    print(f"    Status: {data.get('status')}")
                    print(f"    Message: {data.get('message')}")
                    print(f"    Document ID: {data.get('document_id')}")
                    print(f"    RAG Doc ID: {data.get('rag_document_id')}")
                    print(f"    Chunks: {data.get('chunks_created')}")
                except json.JSONDecodeError as e:
                    print(f"  ✗ Cannot parse JSON response!")
                    print(f"    Error: {e}")
                    print(f"    Response text: {response.text[:500]}")
            elif response.status_code == 302:
                print(f"  ✗ Got redirect (302) - probably not authenticated")
                print(f"    Redirect to: {response.headers.get('Location')}")
            elif response.status_code == 403:
                print(f"  ✗ Got Forbidden (403) - CSRF or permission issue")
                print(f"    Response: {response.text[:200]}")
            else:
                print(f"  ✗ Got unexpected status code!")
                print(f"    Response: {response.text[:500]}")
                
except Exception as e:
    print(f"  ✗ Upload error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70 + "\n")
