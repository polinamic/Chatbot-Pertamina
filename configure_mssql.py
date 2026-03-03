#!/usr/bin/env python
"""
MSSQL Configuration Helper
Helps you set up MSSQL credentials in settings.py
"""

import os
import re
from pathlib import Path


def update_mssql_password():
    """Update MSSQL password in settings.py"""
    settings_file = Path(__file__).parent / 'config' / 'settings.py'
    
    print("\n" + "="*60)
    print("MSSQL CONFIGURATION HELPER")
    print("="*60)
    print("\nThis script will help you configure MSSQL Server connection.")
    print("Current settings file:", settings_file)
    
    # Read current settings
    with open(settings_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract current connection info
    print("\nCurrent MSSQL Configuration:")
    print("-" * 60)
    
    if "'sql_server.pyodbc'" in content:
        print("✅ Engine: sql_server.pyodbc")
    
    # Extract values
    match_name = re.search(r"'NAME':\s*'([^']*)'", content)
    match_user = re.search(r"'USER':\s*'([^']*)'", content)
    match_host = re.search(r"'HOST':\s*'([^']*)'", content)
    match_port = re.search(r"'PORT':\s*'([^']*)'", content)
    
    print(f"✅ Database: {match_name.group(1) if match_name else 'N/A'}")
    print(f"✅ User: {match_user.group(1) if match_user else 'N/A'}")
    print(f"✅ Host: {match_host.group(1) if match_host else 'N/A'}")
    print(f"✅ Port: {match_port.group(1) if match_port else 'N/A'}")
    
    print("\n" + "-" * 60)
    print("MSSQL Server Information:")
    print("-" * 60)
    
    print("\nTo find your MSSQL Server password:")
    print("1. Open SQL Server Management Studio (SSMS)")
    print("2. Login as 'sa' with your password")
    print("3. Or check your MSSQL Server installation notes")
    
    password = input("\nEnter MSSQL 'sa' password: ").strip()
    
    if not password:
        print("❌ Password cannot be empty")
        return False
    
    # Update settings.py
    old_line = "'PASSWORD': 'YourPassword123!',  # Change this to your MSSQL sa password"
    new_line = f"'PASSWORD': '{password}',"
    
    if old_line not in content:
        # Try to find and replace
        match = re.search(r"'PASSWORD':\s*'[^']*'", content)
        if match:
            old_line = match.group(0)
        else:
            print("❌ Could not find PASSWORD line in settings.py")
            return False
    
    new_content = content.replace(old_line, new_line)
    
    if new_content == content:
        print("❌ Could not update settings.py")
        return False
    
    # Backup original
    backup_file = settings_file.with_suffix('.py.backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Write updated
    with open(settings_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("\n✅ Settings updated successfully!")
    print(f"📋 Backup saved to: {backup_file}")
    
    print("\nNext steps:")
    print("1. Ensure MSSQL Server is running")
    print("2. Create database: CREATE DATABASE chatbot_pertamina;")
    print("3. Run migration: python migrate_to_mssql.py")
    
    return True


if __name__ == '__main__':
    import sys
    success = update_mssql_password()
    sys.exit(0 if success else 1)
