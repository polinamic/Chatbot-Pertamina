#!/usr/bin/env python
"""
Quick script to check database schema
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.contrib.auth.models import User
from apps.users.models import UserProfile

print("🔍 Checking database schema...\n")

# Check Django migrations
print("📋 Applied Migrations:")
from django.core.management import call_command
from io import StringIO
import sys as sys_module

out = StringIO()
err = StringIO()
try:
    call_command('showmigrations', 'users', stdout=out, stderr=err)
    output = out.getvalue()
    print(output)
except Exception as e:
    print(f"Error: {e}")

# Check tables
print("\n📊 Database Tables:")
with connection.cursor() as cursor:
    if connection.vendor == 'microsoft':
        # SQL Server specific
        cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME LIKE '%users%'
        """)
    else:
        # SQLite/PostgreSQL
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")

# Check UserProfile table columns
print("\n🔧 UserProfile Table Structure:")
with connection.cursor() as cursor:
    if connection.vendor == 'microsoft':
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'users_userprofile'
        """)
    
    columns = cursor.fetchall()
    if columns:
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
    else:
        print("  ❌ Table not found or empty")

# Test model
print("\n✅ Testing Model Creation:")
try:
    # Create test user
    test_user, created = User.objects.get_or_create(
        username='test_schema_check',
        defaults={'email': 'test@example.com'}
    )
    
    # Create profile
    profile, created = UserProfile.objects.get_or_create(
        user=test_user,
        defaults={
            'role': 'U',
            'company': 'Test',
            'is_verified': False
        }
    )
    
    print(f"✅ Model works! Created profile for {test_user.username}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n✨ Done!")
