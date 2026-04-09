#!/usr/bin/env python
"""
Test multi-turn conversation to ensure chat history works correctly.
"""

import os
import sys
import django
import requests
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from apps.chatbot.models import Conversation, Message

def test_multi_turn_conversation():
    # Create test user
    user = User.objects.filter(username='testuser2').first()
    if not user:
        user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        print(f"✓ Created test user: {user.username} (ID: {user.id})")
    else:
        print(f"✓ Using existing test user: {user.username} (ID: {user.id})")
        # Clear previous conversations for clean test
        Conversation.objects.filter(user=user).delete()
        print(f"  Cleared previous conversations")

    session_id = f"test_session_{int(time.time())}"
    print(f"\n[SESSION] Using session: {session_id}\n")

    # Test messages
    messages = [
        "Printer saya tidak bisa print",
        "Sudah coba restart?",
        "Iya sudah, masih tidak bisa"
    ]

    print("[TEST] Sending 3-turn conversation...\n")
    
    for i, msg in enumerate(messages, 1):
        print(f"Turn {i}: Sending message...")
        
        payload = {
            "query": msg,
            "session_id": session_id,
            "user_id": user.id
        }
        
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/rag/chat/",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        time.sleep(0.5)  # Wait between requests
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '')[:60] + "..."
            print(f"  ✓ Response: {answer}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            return False

    # Verify all messages in database
    print("\n[VERIFICATION] Checking database for conversation history...\n")
    
    conversations = Conversation.objects.filter(user=user).order_by('-created_at')
    
    if conversations.count() == 0:
        print("✗ FAILED: No conversations found")
        return False
    
    for conv in conversations:
        messages = Message.objects.filter(conversation=conv).order_by('created_at')
        print(f"Conversation: {conv.title}")
        print(f"Total messages: {messages.count()}")
        
        if messages.count() != 6:  # 3 user messages + 3 bot messages
            print(f"✗ Expected 6 messages, got {messages.count()}")
            return False
        
        for i, msg in enumerate(messages, 1):
            role = "📤" if msg.role == 'user' else "📥"
            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"  {i}. {role} {msg.role.upper()}: {content}")
    
    print("\n✓ SUCCESS: Multi-turn conversation saved correctly!")
    return True

if __name__ == "__main__":
    try:
        result = test_multi_turn_conversation()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
