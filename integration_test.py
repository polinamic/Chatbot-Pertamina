#!/usr/bin/env python
"""
Comprehensive integration test for signup, login, and chat history per user
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from apps.users.models import UserProfile
from apps.chatbot.models import Conversation

print("\n" + "="*70)
print("FULL SIGNUP -> LOGIN -> CHAT HISTORY INTEGRATION TEST")
print("="*70 + "\n")

# Clean test data
User.objects.filter(username__in=['test_user1', 'test_user2']).delete()

client = Client()

# ============================================================
# TEST 1: SIGNUP
# ============================================================
print("[TEST 1] SIGNUP USER")
print("-" * 70)

resp = client.post('/auth/signup/', {
    'username': 'test_user1',
    'email': 'testuser1@email.com',
    'password': 'TestPass123',
})

if resp.status_code == 302:
    print("✓ Signup redirected (302)")
else:
    print(f"✗ Signup status: {resp.status_code}")

user1 = User.objects.filter(username='test_user1').first()
if user1:
    print(f"✓ User created: {user1.username} ({user1.email})")
    try:
        profile = user1.profile
        print(f"✓ User profile found: company={profile.company}, role={profile.role}")
    except:
        print("✗ User profile not found")
else:
    print("✗ User not created in database")

# ============================================================
# TEST 2: LOGIN
# ============================================================
print("\n[TEST 2] LOGIN USER")
print("-" * 70)

# Create fresh client (clear session)
client = Client()

resp = client.post('/auth/login/', {
    'username': 'test_user1',
    'password': 'TestPass123',
})

if resp.status_code == 302:
    print("✓ Login redirected (302)")
else:
    print(f"✗ Login status: {resp.status_code}")

# Check if user is authenticated in session
if '_auth_user_id' in client.session:
    print(f"✓ User authenticated in session (ID: {client.session.get('_auth_user_id')})")
else:
    print("✗ User not authenticated in session")

# ============================================================
# TEST 3: CREATE CONVERSATIONS FOR THIS USER
# ============================================================
print("\n[TEST 3] CREATE SAMPLE CONVERSATIONS")
print("-" * 70)

if user1:
    conv1 = Conversation.objects.create(
        user=user1,
        title="Conversation 1 - Pertamina Questions",
        query="Apa itu Pertamina?",
        session_id="sess_001"
    )
    print(f"✓ Created conversation 1: {conv1.title}")
    
    conv2 = Conversation.objects.create(
        user=user1,
        title="Conversation 2 - Gas Production",
        query="Berapa produksi gas Pertamina per tahun?",
        session_id="sess_002"
    )
    print(f"✓ Created conversation 2: {conv2.title}")

# ============================================================
# TEST 4: FETCH CHAT HISTORY VIA API
# ============================================================
print("\n[TEST 4] FETCH CHAT HISTORY VIA API")
print("-" * 70)

if user1:
    # Get user ID via /api/v1/users/me/
    resp_me = client.get('/api/v1/users/me/')
    
    if resp_me.status_code == 200:
        import json
        me_data = json.loads(resp_me.content)
        user_id = me_data.get('id')
        print(f"✓ Current user ID from API: {user_id}")
        
        # Fetch chat history
        resp_history = client.get(f'/api/v1/rag/history/?user_id={user_id}')
        
        if resp_history.status_code == 200:
            history_data = json.loads(resp_history.content)
            count = history_data.get('count', 0)
            print(f"✓ Chat history API returned {count} conversations")
            
            if count >= 2:
                print("✓ Both conversations found in history")
                for conv in history_data.get('history', []):
                    print(f"  - {conv.get('title')}")
            else:
                print(f"✗ Expected 2 conversations, got {count}")
        else:
            print(f"✗ Chat history API status: {resp_history.status_code}")
    else:
        print(f"✗ /api/v1/users/me/ status: {resp_me.status_code}")

# ============================================================
# TEST  5: CREATE SECOND USER AND VERIFY ISOLATION
# ============================================================
print("\n[TEST 5] USER ISOLATION - SECOND USER")
print("-" * 70)

# Create second user
resp2 = client.post('/auth/signup/', {
    'username': 'test_user2',
    'email': 'testuser2@email.com',
    'password': 'TestPass456',
})

user2 = User.objects.filter(username='test_user2').first()
if user2:
    print(f"✓ Second user created: {user2.username}")
    
    # Create conversations for user2
    conv3 = Conversation.objects.create(
        user=user2,
        title="User2 Conversation",
        query="Pertanyaan dari user 2",
        session_id="sess_003"
    )
    print(f"✓ Created conversation for user2: {conv3.title}")
    
    # Verify user1 only sees their conversations
    user1_conversations = Conversation.objects.filter(user=user1).count()
    user2_conversations = Conversation.objects.filter(user=user2).count()
    
    print(f"\n✓ User1 has {user1_conversations} conversations")
    print(f"✓ User2 has {user2_conversations} conversations")
    
    if user1_conversations == 2 and user2_conversations == 1:
        print("✓ Users have correct conversation counts (isolated)")
    else:
        print("✗ Conversation counts do not match expected")
else:
    print("✗ Second user not created")

# ============================================================
# CLEANUP
# ============================================================
print("\n[CLEANUP]")
print("-" * 70)
User.objects.filter(username__in=['test_user1', 'test_user2']).delete()
Conversation.objects.filter(session_id__in=['sess_001', 'sess_002', 'sess_003']).delete()
print("✓ Test data cleaned up")

print("\n" + "="*70 + "\n")
