#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.chatbot.models import Conversation, Message
from apps.core.models import Document, ActivityLog
from django.utils import timezone
from datetime import timedelta
import random

print("🌱 Creating sample PERTABOT data...")

# Get or create regular users
users = list(User.objects.filter(is_staff=False))
if len(users) < 3:
    for i in range(1, 4):
        if not User.objects.filter(username=f'user{i}').exists():
            User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@pertamina.com',
                password='password123'
            )
    users = list(User.objects.filter(is_staff=False))

# Create sample conversations
conversation_topics = [
    'Bantuan Reset Password',
    'Troubleshooting Email',
    'VPN Connection Issues',
    'Hardware Request',
    'Software Installation',
    'Network Connectivity',
    'Printer Configuration',
    'Account Permissions'
]

for i, user in enumerate(users):
    for j in range(2):
        conv = Conversation.objects.create(
            user=user,
            title=f'{conversation_topics[(i*2 + j) % len(conversation_topics)]} #{i}-{j}',
            is_archived=random.choice([True, False])
        )
        
        # Create messages for each conversation
        for msg_num in range(random.randint(3, 8)):
            is_user = msg_num % 2 == 0
            Message.objects.create(
                conversation=conv,
                role='user' if is_user else 'assistant',
                content=f'{"User" if is_user else "Bot"} message #{msg_num} dalam percakapan'
            )
            
        # Create activity log
        ActivityLog.objects.create(
            action='CREATE' if j == 0 else 'UPDATE',
            description=f'Conversation: {conv.title}',
            user_id=user.id
        )

# Create sample documents
doc_names = [
    'SOP-Reset-Password.pdf',
    'Network-Troubleshooting.docx',
    'Hardware-Request-Form.pdf',
    'Email-Configuration.pdf',
    'VPN-Setup-Guide.md',
    'Printer-Setup.docx',
    'IT-Policies.pdf'
]

admin_user = User.objects.filter(is_staff=True).first()
if admin_user:
    for doc_name in doc_names:
        doc = Document.objects.create(
            uploaded_by=admin_user,
            file_name=doc_name,
            file_size=random.randint(100000, 5000000),
            file_path=f'documents/{doc_name}',
            is_processed=random.choice([True, False])
        )
        
        ActivityLog.objects.create(
            action='CREATE',
            description=f'Document uploaded: {doc_name}',
            user_id=admin_user.id
        )

# Create sample activity logs
actions = ['CREATE', 'UPDATE', 'DELETE', 'VIEW', 'SEARCH']
descriptions = [
    'User logged in',
    'Document processed',
    'Conversation archived',
    'User role updated',
    'Password reset request',
    'File uploaded',
    'Report generated',
    'Chat conversation created'
]

for _ in range(15):
    ActivityLog.objects.create(
        action=random.choice(actions),
        description=random.choice(descriptions),
        user_id=random.choice(users).id if users else admin_user.id
    )

print("\n✅ Sample data created successfully!")
print(f"   📊 Conversations: {Conversation.objects.count()}")
print(f"   💬 Messages: {Message.objects.count()}")
print(f"   📄 Documents: {Document.objects.count()}")
print(f"   📋 Activity Logs: {ActivityLog.objects.count()}")
print(f"\n✨ Dashboard is ready with live data!")
