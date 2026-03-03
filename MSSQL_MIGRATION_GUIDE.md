# MSSQL Migration Guide

## Prerequisites
- MSSQL Server 2019 or later installed (localhost:1433)
- ODBC Driver 17 for SQL Server installed
- Python packages: pyodbc, django-pyodbc-azure (✅ already installed)
- Django settings.py updated with MSSQL config (✅ already done)

## Current Status
- ✅ SQLite3 database: `db.sqlite3` with 46 messages + test data
- ✅ MSSQL packages installed
- ✅ settings.py configured for MSSQL
- 🔄 MSSQL database not yet created
- 🔄 Migrations not yet applied to MSSQL
- 🔄 Data not yet migrated

## Step 1: Backup SQLite3 Database
```bash
# Create backup
copy db.sqlite3 db.sqlite3.backup

# Verify backup
dir db.sqlite3*
```

## Step 2: Create MSSQL Database
Use SQL Server Management Studio or sqlcmd:

```sql
-- Option A: Using T-SQL
CREATE DATABASE chatbot_pertamina;
GO

-- Verify creation
SELECT name FROM sys.databases WHERE name = 'chatbot_pertamina';
GO
```

## Step 3: Update settings.py with Your MSSQL Password
Edit `config/settings.py` line 85:
```python
'PASSWORD': 'YOUR_ACTUAL_SA_PASSWORD',  # Replace with your sa password
```

## Step 4: Run Django Migrations on MSSQL
```bash
# Verify connection
python manage.py check --database default

# If OK, run migrations
python manage.py migrate

# Verify migration success
python manage.py showmigrations
```

## Step 5: Export Data from SQLite3
Switch back to SQLite3 temporarily:

```python
# In settings.py, temporarily change ENGINE back to:
'ENGINE': 'django.db.backends.sqlite3',
'NAME': 'db.sqlite3',

# Then export:
python manage.py dumpdata > data_backup.json
```

## Step 6: Import Data to MSSQL
Switch settings.py back to MSSQL, then:

```bash
python manage.py loaddata data_backup.json
```

## Step 7: Verify Migration Success
```bash
# Check database connection
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.count()  # Should show number of users

# Exit shell
>>> exit()

# Run tests
python manage.py test

# Start development server
python manage.py runserver
```

## Troubleshooting

### Issue: "Can't create database connection"
- Verify MSSQL Server is running
- Check hostname (localhost) and port (1433)
- Verify sa password is correct
- Test ODBC connection: `python -m pyodbc.tests`

### Issue: "Permission denied"
- Ensure sa user has CREATE DATABASE permission
- Check MSSQL user roles

### Issue: "ODBC Driver 17 not found"
- Install: Microsoft ODBC Driver 17 for SQL Server
- https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-sql-server

### Issue: "TIMESTAMP column" warnings
- Normal MSSQL behavior for auto_now fields
- Does not affect functionality

## Data Verification Checklist
After successful migration:

```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from apps.chatbot.models import Conversation, Message
>>> from apps.core.models import Document, ActivityLog

>>> print(f"Users: {User.objects.count()}")
>>> print(f"Conversations: {Conversation.objects.count()}")  # Should be 9
>>> print(f"Messages: {Message.objects.count()}")  # Should be 46
>>> print(f"Documents: {Document.objects.count()}")  # Should be 7
>>> print(f"Activity Logs: {ActivityLog.objects.count()}")  # Should be 30
```

Expected results after successful migration:
- Users: 5
- Conversations: 9
- Messages: 46
- Documents: 7
- Activity Logs: 30

## Rolling Back (if needed)
If migration fails, revert to SQLite3:

```python
# Edit config/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3',
    }
}
```

## Timeline
- Step 1-2: ~5 minutes
- Step 3-4: ~10 minutes
- Step 5-6: ~15 minutes
- Step 7 (verification): ~5 minutes

**Total estimated time: 35-40 minutes**

## Next Steps After Migration
1. Update production settings with MSSQL credentials
2. Configure connection pooling for better performance
3. Set up database backups
4. Enable SQL Server authentication (if required)
5. Update deployment documentation
