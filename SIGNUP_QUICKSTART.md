# Quick Start - Signup Testing

## 🚀 Setup & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Migrations
```bash
python manage.py migrate
```

### 3. Create Superuser (Optional - untuk admin panel)
```bash
python manage.py createsuperuser
```

### 4. Start Development Server
```bash
python manage.py runserver
```

Server akan berjalan di: `http://localhost:8000`

## 📝 Testing Signup

### Via Web Browser
1. Navigate to: `http://localhost:8000/auth/signup/`
2. Fill form dengan data:
   - **Nama Depan**: John
   - **Nama Belakang**: Doe  
   - **Email**: john.doe@pertamina.com
   - **Perusahaan**: Pertamina Regional
   - **Password**: SecurePass123
   - **Confirm Password**: SecurePass123
   - Check "Saya menerima Syarat & Ketentuan..."

3. Click "Daftar Sekarang"
4. Should redirect to dashboard

### Verifikasi di Database
```bash
# Django shell
python manage.py shell

# Check created user
from django.contrib.auth.models import User
user = User.objects.get(email='john.doe@pertamina.com')
print(user.username)  # john.doe
print(user.first_name)  # John
print(user.profile.company)  # Pertamina Regional
```

### Verifikasi di Admin Panel
1. Go to: `http://localhost:8000/admin/`
2. Login dengan superuser
3. Navigate to "User Profiles"
4. Cek user yang baru dibuat

## ✅ Test Cases

### Valid Signup
```
Input:
- First Name: John
- Last Name: Doe
- Email: john@example.com
- Company: Pertamina
- Password: SecurePass123
- Confirm: SecurePass123

Expected: ✅ User created → Redirect to /dashboard/
```

### Password Mismatch
```
Input:
- Password: SecurePass123
- Confirm: DifferentPass

Expected: ❌ Error: "Password tidak cocok"
```

### Short Password
```
Input:
- Password: Pass1

Expected: ❌ Error: "Password minimal 8 karakter"
```

### Email Exists
```
Input:
- Email: john@example.com (sudah ada)

Expected: ❌ Error: "Email sudah terdaftar"
```

### Missing Required Field
```
Input:
- First Name: (kosong)
- Others: (valid)

Expected: ❌ Error: "Nama depan wajib diisi"
```

## 📊 Database Schema

```sql
-- User Table (Django Built-in)
CREATE TABLE auth_user (
    id INTEGER PRIMARY KEY,
    username VARCHAR(150),
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    email VARCHAR(254),
    password VARCHAR(128),
    is_staff BOOLEAN,
    is_active BOOLEAN,
    date_joined DATETIME
);

-- UserProfile Table (Custom)
CREATE TABLE users_userprofile (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE,
    department VARCHAR(50),
    company VARCHAR(100),
    phone VARCHAR(15),
    bio TEXT,
    is_verified BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);
```

## 🔍 Debugging Tips

### Enable SQL Logging
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

### Check Request/Response
```python
# views.py - tambahkan ini
import logging
logger = logging.getLogger(__name__)

logger.info(f"POST data: {request.POST}")
logger.info(f"User created: {user.username}")
```

### View All Users
```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.all()
>>> User.objects.first().profile
```

## 📋 Form Fields Reference

| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| first_name | Text | ✅ | Non-empty |
| last_name | Text | ✅ | Non-empty |
| email | Email | ✅ | Valid email, unique |
| company | Text | ❌ | Any text |
| password | Password | ✅ | Min 8 chars |
| confirm_password | Password | ✅ | Match password |
| accept_terms | Checkbox | ✅ | Must be checked |

## 🖥️ API Endpoints (REST)

### Register (API)
```
POST /api/v1/users/
Content-Type: application/json

{
    "username": "john.doe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "first_name": "John",
    "last_name": "Doe"
}

Response (201 Created):
{
    "id": 1,
    "username": "john.doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "profile": {
        "id": 1,
        "department": "OTHER",
        "company": "Pertamina",
        "phone": "",
        "bio": ""
    }
}
```

## 🚨 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| ModuleNotFoundError: sentence_transformers | Dependencies not installed | `pip install -r requirements.txt` |
| "No such table: users_userprofile" | Migrations not applied | `python manage.py migrate` |
| CSRF verification failed | CSRF token missing | Add `{% csrf_token %}` ke form |
| Email not validated | Missing email backend config | Check `settings.py` EMAIL_BACKEND |

## 📝 Notes

- Username otomatis generate dari email (bagian sebelum @)
- Jika username sudah ada, akan ditambah angka (john.doe1, john.doe2, etc)
- Password di-hash menggunakan PBKDF2
- Setelah signup, user otomatis login
- Default company adalah "Pertamina" jika kosong

## 📚 Related Files

- Main signup code: `apps/users/views.py` (function: `signup_page`)
- Form template: `apps/users/templates/users/signup.html`
- Models: `apps/users/models.py`
- URLs: `apps/users/urls.py`
- Serializers: `apps/users/serializers.py`

---
**Last Updated**: February 25, 2026
