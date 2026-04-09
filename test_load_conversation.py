#!/usr/bin/env python
"""
Test script untuk memverifikasi load conversation functionality.
"""

import os
import sys
import django
import json
import requests
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from apps.chatbot.models import Conversation, Message

def test_load_conversation():
    print("[SETUP] Getting test user and conversation...\n")
    
    # Get test user and conversation
    user = User.objects.get(username='testuser2')
    conversation = Conversation.objects.filter(user=user).first()
    
    if not conversation:
        print("✗ No conversation found for test user")
        return False
    
    print(f"✓ User: {user.username}")
    print(f"✓ Conversation: {conversation.title}")
    print(f"✓ Conversation ID: {conversation.id}")
    
    # Get messages count from database
    db_messages = Message.objects.filter(conversation=conversation)
    print(f"✓ Messages in database: {db_messages.count()}\n")

    # Test 1: Load conversation via API
    print("[TEST 1] GET /api/v1/rag/conversation/<id>/messages/\n")
    
    response = requests.get(
        f"http://127.0.0.1:8000/api/v1/rag/conversation/{conversation.id}/messages/",
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"✗ Error: {response.status_code}")
        print(f"  Response: {response.text}")
        return False
    
    data = response.json()
    
    if not data.get('success'):
        print(f"✗ API returned success=false")
        return False
    
    print(f"✓ API Response:")
    print(f"  - Success: {data.get('success')}")
    print(f"  - Conversation title: {data['conversation']['title']}")
    print(f"  - Messages returned: {len(data['messages'])}")
    
    # Verify messages match database count
    if len(data['messages']) != db_messages.count():
        print(f"\n✗ FAILED: Message count mismatch!")
        print(f"  Database: {db_messages.count()}, API: {len(data['messages'])}")
        return False
    
    # Display each message
    print(f"\n  Messages:")
    for i, msg in enumerate(data['messages'], 1):
        role = "👤" if msg['role'] == 'user' else "🤖"
        content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
        print(f"    {i}. {role} {msg['role'].upper()}: {content}")
    
    print(f"\n✓ SUCCESS: Conversation loaded via API correctly!")
    return True

if __name__ == "__main__":
    try:
        time.sleep(2)  # Wait for server to start
        result = test_load_conversation()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
