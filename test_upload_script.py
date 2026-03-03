#!/usr/bin/env python
"""
Test script for file upload functionality with proper session handling and CSRF token
"""
import requests
import os
import re
from html.parser import HTMLParser

# Configuration
BASE_URL = 'http://127.0.0.1:8000'
LOGIN_URL = f'{BASE_URL}/auth/login/'
UPLOAD_URL = f'{BASE_URL}/dashboard/api/documents/upload/'
TEST_FILE = 'test_upload.txt'

# Admin credentials
EMAIL = 'admin@pertamina.com'
PASSWORD = 'admin123456'

class CSRFTokenParser(HTMLParser):
    """Parse CSRF token from HTML"""
    def __init__(self):
        super().__init__()
        self.csrf_token = None
    
    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            attrs_dict = dict(attrs)
            if attrs_dict.get('name') == 'csrfmiddlewaretoken':
                self.csrf_token = attrs_dict.get('value')

def extract_csrf_token(html):
    """Extract CSRF token from HTML"""
    parser = CSRFTokenParser()
    parser.feed(html)
    return parser.csrf_token

print("=" * 60)
print("FILE UPLOAD TEST")
print("=" * 60)

# Create session
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})
print("\n1. Creating session...")

# Get login page to extract CSRF token
print("2. Getting login page to extract CSRF token...")
try:
    login_page = session.get(LOGIN_URL)
    csrf_token = extract_csrf_token(login_page.text)
    
    if csrf_token:
        print(f"   ✓ CSRF token found: {csrf_token[:20]}...")
    else:
        print("   ! CSRF token not found in page, trying alternate method...")
        # Try to get from cookies
        if 'csrftoken' in session.cookies:
            csrf_token = session.cookies['csrftoken']
            print(f"   ✓ CSRF token from cookies: {csrf_token[:20]}...")
except Exception as e:
    print(f"   ✗ Error getting login page: {e}")
    exit(1)

# Login - Handle potential login form redirect
print("3. Logging in as admin...")
login_data = {
    'email': EMAIL,
    'password': PASSWORD
}

if csrf_token:
    login_data['csrfmiddlewaretoken'] = csrf_token

try:
    # First POST to login
    login_response = session.post(LOGIN_URL, data=login_data, allow_redirects=False)
    print(f"   Login response status: {login_response.status_code}")
    print(f"   Location header: {login_response.headers.get('Location', 'None')}")
    
    # Check if redirected (302) which means successful login
    if login_response.status_code == 302:
        redirect_path = login_response.headers.get('Location')
        # Convert relative path to full URL
        if redirect_path.startswith('/'):
            redirect_url = BASE_URL + redirect_path
        else:
            redirect_url = redirect_path
        print(f"   ✓ Redirected to: {redirect_url}")
        # Follow redirect
        follow_response = session.get(redirect_url, allow_redirects=True)
        print(f"   ✓ Follow redirect status: {follow_response.status_code}")
    elif login_response.status_code == 200:
        print(f"   ! Returned 200, checking if login was successful...")
        if 'dashboard' in login_response.url or 'logout' in login_response.text.lower():
            print(f"   ✓ Appears to be logged in")
        else:
            print(f"   ! May not be logged in, continuing anyway...")
    
    print(f"   ✓ Current cookies: {[f'{k}' for k in session.cookies.keys()]}")
    if 'sessionid' in session.cookies:
        print(f"   ✓ SESSION ID FOUND: {session.cookies.get('sessionid', 'NOT SET')[:20]}...")
    
except Exception as e:
    print(f"   ✗ Login error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Get fresh CSRF token for upload
print("\n4. Getting CSRF token for upload...")
try:
    csrf_response = session.get(UPLOAD_URL.replace('upload/', '').rstrip('/') + '/')
    if 'csrftoken' in session.cookies:
        upload_csrf = session.cookies['csrftoken']
        print(f"   ✓ Upload CSRF token ready: {upload_csrf[:20]}...")
    else:
        upload_csrf = csrf_token
        print(f"   ! Using login CSRF token for upload")
except Exception as e:
    print(f"   ! Error getting upload CSRF: {e}")
    upload_csrf = csrf_token

# Test file upload
print(f"\n5. Uploading test file: {TEST_FILE}...")
if not os.path.exists(TEST_FILE):
    print(f"   ✗ Test file not found: {TEST_FILE}")
    exit(1)

try:
    with open(TEST_FILE, 'rb') as f:
        files = {'file': (TEST_FILE, f, 'text/plain')}
        headers = {
            'X-CSRFToken': upload_csrf if upload_csrf else ''
        }
        print(f"   Headers: {headers}")
        print(f"   Cookies: sessionid={session.cookies.get('sessionid', 'NOT SET')}")
        upload_response = session.post(UPLOAD_URL, files=files, headers=headers)
    
    print(f"   ✓ Upload request sent (Status: {upload_response.status_code})")
    print(f"   Response length: {len(upload_response.text)} bytes")
    
    # Parse response
    if upload_response.status_code == 200:
        try:
            response_data = upload_response.json()
            print(f"\n6. Server Response:")
            print(f"   Status: {response_data.get('status')}")
            print(f"   Message: {response_data.get('message')}")
            print(f"   Document ID: {response_data.get('document_id')}")
            print(f"   RAG Document ID: {response_data.get('rag_document_id')}")
            print(f"   Chunks Created: {response_data.get('chunks_created')}")
            
            if response_data.get('status') == 'success':
                print("\n✓ Upload test PASSED!")
            else:
                print("\n✗ Upload test FAILED!")
                print(f"   Error: {response_data.get('message')}")
        except requests.exceptions.JSONDecodeError as e:
            print(f"   ✗ JSON decode error: {e}")
            print(f"   Response text: {upload_response.text[:500]}")
    elif upload_response.status_code == 302:
        print(f"   ! Redirected to login (need authentication)")
        print(f"   Redirect URL: {upload_response.headers.get('Location')}")
    else:
        print(f"   ✗ Upload failed with status {upload_response.status_code}")
        print(f"   Response preview: {upload_response.text[:500]}")

except Exception as e:
    print(f"   ✗ Upload error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
