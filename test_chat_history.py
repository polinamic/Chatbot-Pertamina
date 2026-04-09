#!/usr/bin/env python
"""
Test script untuk verifikasi chat history saving functionality.
"""

import os
import sys
import django
import json
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from apps.chatbot.models import Conversation, Message

def test_chat_history():
    # Create test user
    user = User.objects.filter(username='testuser').first()
    if not user:
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        print(f"✓ Created test user: {user.username} (ID: {user.id})")
    else:
        print(f"✓ Using existing test user: {user.username} (ID: {user.id})")

    # Test 1: Send chat message with user_id
    print("\n[TEST 1] Sending chat message with user_id...")
    
    payload = {
        "query": "Bagaimana cara mengatasi masalah koneksi internet?",
        "session_id": "test_session_123",
        "user_id": user.id
    }
    
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/rag/chat/",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Chat response received:")
        print(f"  - Answer length: {len(data.get('answer', ''))}")
        print(f"  - Session ID: {data.get('session_id')}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

    # Test 2: Check if messages were saved to database
    print("\n[TEST 2] Checking if messages were saved to database...")
    
    conversations = Conversation.objects.filter(user=user)
    print(f"✓ Found {conversations.count()} conversation(s) for {user.username}")
    
    for conv in conversations:
        messages = Message.objects.filter(conversation=conv)
        print(f"\n  Conversation: {conv.title}")
        print(f"  Created: {conv.created_at}")
        print(f"  Messages: {messages.count()}")
        
        for msg in messages:
            role = "👤 User" if msg.role == 'user' else "🤖 Bot"
            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"    {role}: {content}")
            print(f"       Created: {msg.created_at}")

    if conversations.count() > 0:
        print("\n✓ SUCCESS: Chat history is being saved to database!")
        return True
    else:
        print("\n✗ FAILED: No conversations found in database")
        return False

if __name__ == "__main__":
    try:
        result = test_chat_history()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
