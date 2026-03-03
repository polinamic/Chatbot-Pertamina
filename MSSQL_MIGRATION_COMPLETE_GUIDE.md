# Complete MSSQL Migration Guide for PERTABOT

## Quick Summary
You have 3 migration scripts ready to use:
1. **configure_mssql.py** - Set MSSQL password securely
2. **migrate_to_mssql.py** - Automated migration (7 steps)
3. **MSSQL_MIGRATION_GUIDE.md** - Complete reference documentation

## Pre-Migration Checklist

### Requirements
- [ ] MSSQL Server 2019+ installed and running
- [ ] MSSQL running on localhost:1433
- [ ] ODBC Driver 17 for SQL Server installed
- [ ] Python packages: pyodbc, django-pyodbc-azure (✅ Already installed)
- [ ] MSSQL sa user password known
- [ ] Database backup exists (optional but recommended)

### Installation Check
```bash
# Check ODBC Driver
python -c "import pyodbc; print(pyodbc.drivers())"
# Look for: "ODBC Driver 17 for SQL Server"

# Check Django packages
python -c "import sql_server.pyodbc; print('✅ django-pyodbc-azure installed')"
python -c "import pyodbc; print('✅ pyodbc installed')"
```

## Step-by-Step Migration Process

### Phase 1: Configuration (5 minutes)

#### Step 1.1: Create MSSQL Database
Open **SQL Server Management Studio** or **Azure Data Studio**:

```sql
-- Connect as 'sa' user
CREATE DATABASE chatbot_pertamina;
GO

-- Verify creation
SELECT name FROM sys.databases WHERE name = 'chatbot_pertamina';
GO
```

**Or via command line (sqlcmd):**
```bash
sqlcmd -S localhost -U sa -P "YourPassword" -Q "CREATE DATABASE chatbot_pertamina;"
```

#### Step 1.2: Configure MSSQL Password
```bash
python configure_mssql.py
```

This script will:
1. Display current MSSQL configuration
2. Prompt for sa password
3. Update settings.py securely
4. Create a backup of original settings.py

**Expected output:**
```
============================================================
MSSQL CONFIGURATION HELPER
============================================================

Current MSSQL Configuration:
------------------------------------------------------------
✅ Engine: sql_server.pyodbc
✅ Database: chatbot_pertamina
✅ User: sa
✅ Host: localhost
✅ Port: 1433

Enter MSSQL 'sa' password:
[Enter password here]

✅ Settings updated successfully!
📋 Backup saved to: config/settings.py.backup
```

#### Step 1.3: Verify Configuration
```bash
python manage.py check

# Expected: System check identified no issues (0 silenced).
```

### Phase 2: Data Export (5 minutes)

#### Step 2.1: Backup SQLite3
```bash
# Create backup
copy db.sqlite3 backups/db_backup_$(Get-Date -Format "yyyyMMdd_HHmmss").sqlite3

# Or manually (Windows):
copy db.sqlite3 db.sqlite3.backup
```

#### Step 2.2: Export Data
The migration script does this automatically, but if you need manual export:

```bash
# This creates data_export.json with all SQLite3 data
python manage.py dumpdata > data_export.json

# Verify export
dir data_export.json  # Should show file size > 10KB
```

### Phase 3: Automated Migration (15 minutes)

#### Step 3.1: Run Automated Migration
```bash
python migrate_to_mssql.py
```

**Expected output:**
```
============================================================
STARTING MSSQL MIGRATION
============================================================
Timestamp: [Current timestamp]
Backup directory: backups

============================================================
STEP 1: Backing up SQLite3 database...
============================================================
✅ Backup created: backups/db_backup_20250224_143022.sqlite3
   Size: 20,480 bytes

============================================================
STEP 2: Counting existing data in SQLite3...
============================================================
   Users: 5
   Conversations: 9
   Messages: 46
   Documents: 7
   Activity Logs: 30
   Total records: 97
✅ Data counted successfully

============================================================
STEP 3: Exporting data from SQLite3 to JSON...
============================================================
   Dumping all data to JSON...
✅ Data exported to: backups/data_export_20250224_143022.json
   Size: 45,824 bytes

============================================================
STEP 4: Checking MSSQL connection...
============================================================
   Verifying Django settings...
✅ MSSQL configuration verified

============================================================
STEP 5: Running Django migrations on MSSQL...
============================================================
   Applying migrations...
Operations to perform:
  Apply all migrations: admin, auth, chatbot, contenttypes, core, sessions, users
Running migrations:
  Applying auth.0001_initial...
  Applying auth.0002_alter_permission_add_options...
  ...
✅ Migrations completed successfully

============================================================
STEP 6: Importing data to MSSQL...
============================================================
   Loading data...
Installed 97 object(s) from 1 fixture(s)
✅ Data imported successfully

============================================================
STEP 7: Verifying migration...
============================================================
   SQLite3 → MSSQL comparison:
   Users:         5 → 5
   Conversations: 9 → 9
   Messages:      46 → 46
   Documents:     7 → 7
   Activity Logs: 30 → 30
✅ All data verified - Migration successful!

============================================================
MIGRATION REPORT
============================================================

📋 Report saved to: backups/migration_report_20250224_143022.txt

============================================================
✅ MIGRATION COMPLETED
============================================================

Next steps:
1. Test the dashboard: python manage.py runserver
2. Visit http://127.0.0.1:8000/dashboard/
3. Login with: admin / admin123456

📁 Backups saved to: backups
```

### Phase 4: Verification (10 minutes)

#### Step 4.1: Test Database Connection
```bash
python manage.py shell

>>> from django.contrib.auth.models import User
>>> from apps.chatbot.models import Conversation, Message
>>> from apps.core.models import Document, ActivityLog

# Check record counts
>>> print(f"Users: {User.objects.count()}")
>>> print(f"Conversations: {Conversation.objects.count()}")
>>> print(f"Messages: {Message.objects.count()}")
>>> print(f"Documents: {Document.objects.count()}")
>>> print(f"Activity Logs: {ActivityLog.objects.count()}")

# Test sample data
>>> admin = User.objects.get(username='admin')
>>> print(f"Admin user: {admin.email}")
>>> conv = Conversation.objects.first()
>>> print(f"First conversation: {conv.title}")

>>> exit()
```

#### Step 4.2: Start Development Server
```bash
python manage.py runserver
```

**Expected console output:**
```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
February 24, 2025 - 14:30:22
Django version 3.2.13, using settings 'config.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

#### Step 4.3: Test Dashboard
1. Open browser: http://127.0.0.1:8000/
2. Login page should appear
3. Login with:
   - **Username:** admin
   - **Password:** admin123456
4. Should see dashboard with statistics
5. Navigate through all dashboard sections
6. Verify that all data displays correctly

#### Step 4.4: Run Test Suite
```bash
python manage.py test

# Should show:
# Ran X tests in Xs
# OK
```

## Troubleshooting

### Problem 1: "Connection refused" or "Can't open a connection to SQL Server"

**Solution:**
1. Verify MSSQL Server is running:
   ```bash
   # Windows Services
   Get-Service -Name "MSSQL*"
   
   # Should show: MSSQLSERVER     Running
   ```

2. Check MSSQL is listening on port 1433:
   ```bash
   netstat -an | findstr "1433"
   
   # Should show: TCP    0.0.0.0:1433    0.0.0.0:0    LISTENING
   ```

3. Test connection with sqlcmd:
   ```bash
   sqlcmd -S localhost -U sa -P "YOUR_PASSWORD"
   1> exit
   ```

### Problem 2: "The specified ODBC driver could not be loaded due to system error code 127"

**Solution:**
1. Install ODBC Driver 17:
   - Download: https://www.microsoft.com/en-us/download/details.aspx?id=53591
   - Run installer
   - Restart Python

2. Verify installation:
   ```bash
   python -c "import pyodbc; print(pyodbc.drivers())"
   ```

### Problem 3: "Login failed for user 'sa'"

**Solution:**
1. Verify sa password in settings.py is correct
2. Test sa login with SSMS
3. Check SQL Server authentication is enabled:
   - Open SSMS → Connect to server
   - Right-click Server → Properties
   - Security tab → Check "SQL Server and Windows Authentication mode"

### Problem 4: "Database 'chatbot_pertamina' does not exist"

**Solution:**
```bash
# Create database
sqlcmd -S localhost -U sa -P "PASSWORD"
1> CREATE DATABASE chatbot_pertamina;
2> GO

# Verify
1> SELECT name FROM sys.databases;
2> GO
```

### Problem 5: "TIMESTAMP column preference" warnings

**This is normal.** MSSQL generates warnings about TIMESTAMP columns for Django's auto_now fields. It doesn't affect functionality.

## Rollback Plan (If Migration Fails)

### Option A: Revert to SQLite3 (Quick)
```python
# Edit config/settings.py - Revert DATABASES:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3',
    }
}
```

### Option B: Restore from Backup (Recommended)
```bash
# MSSQL - Drop database
sqlcmd -S localhost -U sa -P "PASSWORD" -Q "DROP DATABASE chatbot_pertamina;"

# Create fresh database and re-run migrate_to_mssql.py
```

### Option C: Manual Revert
```bash
# 1. Restore SQLite3 backup
copy db.sqlite3.backup db.sqlite3

# 2. Revert settings.py
copy config/settings.py.backup config/settings.py

# 3. Start server
python manage.py runserver
```

## Settings.py Reference

### Current MSSQL Configuration
```python
DATABASES = {
    'default': {
        'ENGINE': 'sql_server.pyodbc',
        'NAME': 'chatbot_pertamina',
        'USER': 'sa',
        'PASSWORD': '[Your password here]',
        'HOST': 'localhost',
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            # Optional advanced settings:
            # 'TrustServerCertificate': 'yes',  # For self-signed certs
            # 'Connection Timeout': 30,
        }
    }
}
```

## Migration Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Create MSSQL Database | 2 min | ⏳ Pending |
| 1 | Configure MSSQL Password | 3 min | ⏳ Pending |
| 1 | Verify Connection | 2 min | ⏳ Pending |
| 2 | Backup SQLite3 | 1 min | ⏳ Pending |
| 2 | Export Data | 2 min | ⏳ Pending |
| 3 | Run Automated Migration | 10-15 min | ⏳ Pending |
| 4 | Verify Data | 5 min | ⏳ Pending |
| 4 | Test Dashboard | 5 min | ⏳ Pending |
| **Total** | | **30-35 min** | |

## Success Criteria
After migration, you should have:

✅ **Database Connection**
- MSSQL Server connection working
- No connection errors in logs
- `django.setup()` completes successfully

✅ **Data Migration**
- All 5 users migrated
- All 9 conversations migrated
- All 46 messages migrated
- All 7 documents migrated
- All 30 activity logs migrated

✅ **Dashboard Functionality**
- Login works with admin/admin123456
- Dashboard loads without errors
- All statistics display correctly
- All pages accessible
- Data displays properly

✅ **Backups**
- SQLite3 backup created
- Data export JSON created
- Migration report generated

## Post-Migration Tasks

### 1. Production Configuration
```python
# Update settings.py:
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']

# Enable CSRF
CSRF_TRUSTED_ORIGINS = ['https://your-domain.com']

# Security headers
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### 2. Setup Database Backups
```bash
# Create backup script (backup_mssql.sql)
BACKUP DATABASE chatbot_pertamina 
TO DISK = 'C:\Backups\chatbot_pertamina_backup.bak'
```

### 3. Monitor Performance
```bash
# Check slow queries
python manage.py shell
>>> from django.db import connection
>>> print(connection.queries_log)
```

### 4. Setup Connection Pooling
```python
# Optional: Add to DATABASES OPTIONS
'CONN_MAX_AGE': 600,  # Keep connections for 10 minutes
```

## Additional Resources

- [Django SQL Server Documentation](https://github.com/ESSolutions/django-pyodbc-azure)
- [MSSQL Server Management Studio Download](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms)
- [ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-sql-server)
- [Django Database Management](https://docs.djangoproject.com/en/3.2/ref/django-admin/#migrate)

## Support

If you encounter issues:
1. Check the migration report: `backups/migration_report_*.txt`
2. Review troubleshooting section above
3. Check MSSQL Server logs
4. Run: `python manage.py check --database default`

## Summary

**You now have everything needed to migrate PERTABOT from SQLite3 to MSSQL Server:**

1. ✅ Required Python packages installed
2. ✅ Django settings configured
3. ✅ Migration script created
4. ✅ Configuration helper script ready
5. ✅ Complete documentation

**Next, you need to:**
1. Create MSSQL database
2. Run configure_mssql.py
3. Run migrate_to_mssql.py
4. Test the dashboard

**Total time required: 30-35 minutes**

Good luck! 🚀
