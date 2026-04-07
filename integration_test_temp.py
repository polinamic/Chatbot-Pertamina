#!/usr/bin/env python
"""
Comprehensive integration  for signup, login, and  history per 
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
if 'server' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('server')
django.setup()

from django.contrib.auth.models import 
from django. import Client
from apps.s.models import Profile
from apps.bot.models import Conversation

print("\n" + "="*70)
print(" SIGNUP -> LOGIN ->  HISTORY INTEGRATION ")
print("="*70 + "\n")

# Clean  data
.objects.filter(name__in=['_1', '_2']).delete()

client = Client()

# ============================================================
#  1: SIGNUP
# ============================================================
print("[ 1] SIGNUP ")
print("-" * 70)

resp = client.post('/auth/signup/', {
    'name': '_1',
    'email': '1@email.com',
    'password': 'Pass123',
})

if resp.status_code == 302:
    print("✓ Signup redirected (302)")
else:
    print(f"✗ Signup status: {resp.status_code}")

1 = .objects.filter(name='_1').first()
if 1:
    print(f"✓  created: {1.name} ({1.email})")
    try:
        profile = 1.profile
        print(f"✓  profile found: company={profile.company}, role={profile.role}")
    except:
        print("✗  profile not found")
else:
    print("✗  not created in database")

# ============================================================
#  2: LOGIN
# ============================================================
print("\n[ 2] LOGIN ")
print("-" * 70)

# Create fresh client (clear session)
client = Client()

resp = client.post('/auth/login/', {
    'name': '_1',
    'password': 'Pass123',
})

if resp.status_code == 302:
    print("✓ Login redirected (302)")
else:
    print(f"✗ Login status: {resp.status_code}")

# Check if  is authenticated in session
if '_auth__id' in client.session:
    print(f"✓  authenticated in session (ID: {client.session.get('_auth__id')})")
else:
    print("✗  not authenticated in session")

# ============================================================
#  3: CREATE  FOR THIS 
# ============================================================
print("\n[ 3] CREATE SAMPLE ")
print("-" * 70)

if 1:
    conv1 = Conversation.objects.create(
        =1,
        title="Conversation 1 - Pertamina Questions",
        query="Apa itu Pertamina?",
        session_id="sess_001"
    )
    print(f"✓ Created conversation 1: {conv1.title}")
    
    conv2 = Conversation.objects.create(
        =1,
        title="Conversation 2 - Gas Production",
        query="Berapa produksi gas Pertamina per tahun?",
        session_id="sess_002"
    )
    print(f"✓ Created conversation 2: {conv2.title}")

# ============================================================
#  4: FETCH  HISTORY VIA 
# ============================================================
print("\n[ 4] FETCH  HISTORY VIA ")
print("-" * 70)

if 1:
    # Get  ID via //v1/s/me/
    resp_me = client.get('//v1/s/me/')
    
    if resp_me.status_code == 200:
        import json
        me_data = json.loads(resp_me.content)
        _id = me_data.get('id')
        print(f"✓ Current  ID from : {_id}")
        
        # Fetch  history
        resp_history = client.get(f'//v1/rag/history/?_id={_id}')
        
        if resp_history.status_code == 200:
            history_data = json.loads(resp_history.content)
            count = history_data.get('count', 0)
            print(f"✓  history  returned {count} ")
            
            if count >= 2:
                print("✓ Both  found in history")
                for conv in history_data.get('history', []):
                    print(f"  - {conv.get('title')}")
            else:
                print(f"✗ Expected 2 , got {count}")
        else:
            print(f"✗  history  status: {resp_history.status_code}")
    else:
        print(f"✗ //v1/s/me/ status: {resp_me.status_code}")

# ============================================================
#   5: CREATE SECOND  AND VERIFY 
# ============================================================
print("\n[ 5]   - SECOND ")
print("-" * 70)

# Create second 
resp2 = client.post('/auth/signup/', {
    'name': '_2',
    'email': '2@email.com',
    'password': 'Pass456',
})

2 = .objects.filter(name='_2').first()
if 2:
    print(f"✓ Second  created: {2.name}")
    
    # Create  for 2
    conv3 = Conversation.objects.create(
        =2,
        title="2 Conversation",
        query="Pertanyaan dari  2",
        session_id="sess_003"
    )
    print(f"✓ Created conversation for 2: {conv3.title}")
    
    # Verify 1 only sees their 
    1_ = Conversation.objects.filter(=1).count()
    2_ = Conversation.objects.filter(=2).count()
    
    print(f"\n✓ 1 has {1_} ")
    print(f"✓ 2 has {2_} ")
    
    if 1_ == 2 and 2_ == 1:
        print("✓ s have correct conversation counts (isolated)")
    else:
        print("✗ Conversation counts do not match expected")
else:
    print("✗ Second  not created")

# ============================================================
# CLEANUP
# ============================================================
print("\n[CLEANUP]")
print("-" * 70)
.objects.filter(name__in=['_1', '_2']).delete()
Conversation.objects.filter(session_id__in=['sess_001', 'sess_002', 'sess_003']).delete()
print("✓  data cleaned up")

print("\n" + "="*70 + "\n")
