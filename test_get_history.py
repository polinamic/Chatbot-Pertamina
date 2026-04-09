#!/usr/bin/env python
"""
Test retrieving chat history from backend.
"""

import requests
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User

def test_get_chat_history():
    # Get testuser2 (should have conversation history from previous test)
    user = User.objects.get(username='testuser2')
    print(f"Testing chat history retrieval for user: {user.username} (ID: {user.id})\n")
    
    # Call get_chat_history endpoint
    print("[TEST] Calling GET /api/v1/rag/history/...\n")
    
    response = requests.get(
        f"http://127.0.0.1:8000/api/v1/rag/history/?user_id={user.id}",
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"✗ Error: {response.status_code}")
        print(f"  Response: {response.text}")
        return False
    
    data = response.json()
    print(f"✓ API Response:")
    print(f"  Success: {data.get('success')}")
    print(f"  Count: {data.get('count')}")
    print(f"  Histories:")
    
    for conv in data.get('history', []):
        print(f"\n    📌 ID: {conv['id']}")
        print(f"       Title: {conv['title']}")
        print(f"       Created: {conv['created_at']}")
        print(f"       Updated: {conv['updated_at']}")
    
    # Verify we got conversation data
    if data.get('count', 0) > 0:
        print(f"\n✓ SUCCESS: Chat history retrieved from backend!")
        return True
    else:
        print(f"\n✗ FAILED: No conversation history found")
        return False

if __name__ == "__main__":
    try:
        result = test_get_chat_history()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
