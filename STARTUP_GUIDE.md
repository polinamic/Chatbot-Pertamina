# 🚀 STARTUP GUIDE - Chatbot Pertamina dengan MSSQL + Llama 3.8b

## ✅ Konfigurasi Saat Ini

```
✅ MSSQL Server 2019
   - Localhost
   - Database: chatbot_pertamina
   - 24 existing tables
   - Windows Authentication

✅ Django Framework
   - MSSQL Backend Configured
   - Migrations Applied
   - Settings Updated

✅ Llama 3.8b Model
   - Downloaded & Ready
   - Via Ollama Service
   - Port: http://localhost:11434

✅ Signup System
   - Forms & Validation Ready
   - Database Connected
   - Responsive UI Implemented
```

## 🎯 Langkah-Langkah Startup

### Langkah 1️⃣: Jalankan MSSQL Server Service
```bash
# Pastikan SQL Server service running
# Control Panel → Services → SQL Server (MSSQLSERVER)
# Atau gunakan SQL Server Configuration Manager
```

**Verifikasi:**
```bash
python test_mssql_connection.py
```

### Langkah 2️⃣: Jalankan Ollama Service (Terminal 1)
```bash
# Terminal baru
ollama serve
```

**Expected Output:**
```
starting ollama serve
listening on 127.0.0.1:11434
```

**Verifikasi Llama:**
```bash
python test_llama.py
```

### Langkah 3️⃣: Jalankan Django Development Server (Terminal 2)
```bash
# Masuk ke project directory
cd "c:\AAAAAAAAAAAAAAAAAAA\Semester 6\Pertamina\Chatbot-Pertamina"

# Activate virtual environment
.\.venv\Scripts\activate

# Run development server
python manage.py runserver
```

**Expected Output:**
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Langkah 4️⃣: Access Web Interface (Browser)

| Fungsi | URL |
|--------|-----|
| 🏠 Home | http://localhost:8000 |
| 📝 Signup | http://localhost:8000/auth/signup/ |
| 🔐 Login | http://localhost:8000/auth/login/ |
| 👨‍💼 Admin | http://localhost:8000/admin/ |
| 📊 API | http://localhost:8000/api/v1/ |
| 🚀 Dashboard | http://localhost:8000/dashboard/ |

## 📋 Test Signup Flow

### Test 1: Valid Signup
```
URL: http://localhost:8000/auth/signup/

Form Data:
├─ Nama Depan: John
├─ Nama Belakang: Doe
├─ Email: john.doe@pertamina.com
├─ Perusahaan: Pertamina Regional
├─ Password: SecurePass123
├─ Konfirmasi: SecurePass123
└─ Terms: ✓ Checked

Expected Result:
✅ User Created
✅ Auto Login
✅ Redirect to Dashboard
```

### Test 2: Validation Errors
```
Try dengan data invalid:
- Kosong field required
- Password < 8 karakter
- Password tidak match
- Email sudah exist
- Terms tidak checked

Expected Result:
❌ Error message ditampilkan
❌ Form tetap diisi dengan data yang valid
```

### Test 3: Database Verification
```bash
# Django Shell
python manage.py shell

# Check created user
from django.contrib.auth.models import User
from apps.users.models import UserProfile

users = User.objects.all()
print(f"Total Users: {users.count()}")

# Check specific user
user = User.objects.get(email='john.doe@pertamina.com')
print(f"Username: {user.username}")
print(f"Email: {user.email}")
print(f"Company: {user.profile.company}")
print(f"Is Verified: {user.profile.is_verified}")
```

### Test 4: Admin Panel
```
URL: http://localhost:8000/admin/

1. Login dengan superuser (jika belum ada, buat dulu):
   python manage.py createsuperuser

2. Navigate to "User Profiles"

3. Lihat user yang telah signup

4. Edit profile untuk set verification status
```

## 🧪 Middleware & Dependencies

### Installed Packages
```bash
✅ Django 4.2.9
✅ djangorestframework 3.14.0
✅ mssql-django 1.4
✅ pyodbc 4.0.39
✅ sentence-transformers 2.2.2
✅ faiss-cpu 1.7.4
✅ ollama (untuk Llama client)
✅ requests (untuk Ollama API)
```

### Check Installation
```bash
pip list | findstr "django\|mssql\|sentence\|faiss\|ollama"
```

## 📊 Database Tables untuk Signup

```
✅ auth_user
   └─ Stores Django user credentials
   └─ Fields: username, email, password (hashed), first_name, last_name

✅ users_userprofile  
   └─ Stores custom user profile
   └─ Fields: department, company, phone, bio, is_verified, created_at, updated_at

✅ django_session
   └─ Session management untuk authenticated users

✅ django_migrations
   └─ Track applied migrations
```

## 🔐 Security Checklist

```
☑ Password Hashing: PBKDF2 (Django default)
☑ CSRF Protection: {% csrf_token %} di form
☑ SQL Injection: Django ORM parameterized queries
☑ Windows Authentication: Trusted_Connection=yes
☑ Session Security: Django session framework
☑ Input Validation: Server-side + client-side
```

## 🚨 Troubleshooting

### Issue: "MSSQL Connection Failed"
```bash
# Solution:
1. Verify SQL Server Service running
   → SQL Server Configuration Manager → Services

2. Check database exists:
   python test_mssql_connection.py

3. Verify ODBC Driver:
   Control Panel → Administrative Tools → ODBC Data Sources
   → System DSN → Check "ODBC Driver 17 for SQL Server"

4. If issue persists, use SQL Authentication:
   DATABASES = {
       'default': {
           'ENGINE': 'mssql',
           'NAME': 'chatbot_pertamina',
           'USER': 'sa',
           'PASSWORD': 'your_password',
           'HOST': 'localhost',
           'OPTIONS': {
               'driver': 'ODBC Driver 17 for SQL Server',
           }
       }
   }
```

### Issue: "Ollama Service Not Running"
```bash
# Solution:
1. Check if Ollama service running:
   → Task Manager → Services tab → Ollama

2. Start Ollama manually:
   ollama serve

3. Verify port 11434 is open:
   netstat -an | findstr "11434"

4. Test connection:
   python test_llama.py
```

### Issue: "Signup Form Not Submitting"
```bash
# Check:
1. Browser Console (F12) untuk JavaScript errors
2. Django logs di terminal
3. CSRF token ada di form
4. All required fields filled
5. Database connection working
```

## 📝 Create Superuser (Admin)

Jika belum ada superuser, buat dengan:

```bash
python manage.py createsuperuser

# Input:
# Username: admin
# Email: admin@pertamina.com
# Password: (masukkan password aman)
```

Kemudian login di: http://localhost:8000/admin/

## 🎨 Customize Email (Optional)

Untuk mengirim email konfirmasi, update settings.py:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = 'your_app_password'
DEFAULT_FROM_EMAIL = 'noreply@chatbot-pertamina.com'
```

## 📈 Performance Tips

### 1. Enable Query Caching
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

### 2. Use Database Connection Pooling
```python
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'OPTIONS': {
            'pool': {
                'min_size': 5,
                'max_size': 20,
            }
        }
    }
}
```

### 3. Enable Static Files Compression
```bash
python manage.py collectstatic
```

## 📞 Support & Debug

### Enable Debug Logging
```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### View SQL Queries
```bash
python manage.py shell

from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as ctx:
    # Your Django ORM query here
    from apps.users.models import UserProfile
    profiles = UserProfile.objects.all()

print(f"Total queries: {len(ctx)}")
for query in ctx:
    print(query['sql'])
```

## ✅ Final Checklist

```
Pre-Startup:
□ MSSQL Server service running
□ SQL Server Management Studio open (optional)
□ Python virtual environment activated
□ All dependencies installed (pip list)
□ Django settings.py updated for MSSQL

Startup:
□ Ollama service running (terminal 1)
□ Django development server running (terminal 2)
□ Browser access http://localhost:8000

Testing:
□ test_mssql_connection.py passed
□ test_llama.py passed
□ Signup form accessible
□ Can create new user
□ User appears in admin panel
□ User data stored in MSSQL

Cleanup:
□ Remove debug files
□ Update DEBUG = False (production)
□ Setup ALLOWED_HOSTS
□ Configure static/media files
□ Setup email backend
```

## 🎉 Semuanya Siap!

Sekarang sistem Chatbot Pertamina siap digunakan dengan:
- ✅ MSSQL Server sebagai database
- ✅ Django sebagai web framework  
- ✅ Llama 3.8b sebagai LLM engine
- ✅ Signup system yang lengkap dan aman

**Enjoy!** 🚀

---
**Version**: 1.0  
**Created**: February 25, 2026  
**Last Updated**: February 25, 2026
