# 🔐 Panduan Authentication Backend - Chatbot Pertamina

## 📋 Daftar Isi
1. [Membuat Admin User](#membuat-admin-user)
2. [Endpoint API Authentication](#endpoint-api-authentication)
3. [Perubahan yang Dilakukan](#perubahan-yang-dilakukan)
4. [Panduan Testing](#panduan-testing)

---

## 🔑 Membuat Admin User

Tersedia **2 cara** untuk membuat admin user:

### Cara 1: Menggunakan Management Command (Recommended)
Perintah ini lebih mudah dan terintegrasi dengan Django:

```bash
# Dengan input interaktif
python manage.py create_admin

# Dengan parameter (non-interactive)
python manage.py create_admin --username admin --email admin@pertamina.com --password Admin123! --firstname Admin --lastname User
```

**Contoh Penggunaan:**
```bash
$ python manage.py create_admin
Masukkan username: admin
Masukkan email: admin@pertamina.com
Masukkan password: 
Konfirmasi password: 
Masukkan first name (default: Admin): Admin
Masukkan last name (default: User): User

✓ Admin user berhasil dibuat
  Username: admin
  Email: admin@pertamina.com
  Full Name: Admin User
  Role: Admin
```

### Cara 2: Menggunakan Standalone Python Script
Script standalone tanpa Django management:

```bash
python create_admin_user.py
```

**Fitur:**
- ✅ Input validation yang ketat
- ✅ Password strength validation
- ✅ Konfirmasi password
- ✅ User-friendly output dengan emoji

---

## 🌐 Endpoint API Authentication

### 1. **Sign Up** (POST)
```
POST /api/users/auth/signup/
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@pertamina.com",
  "password": "StrongPass123",
  "password_confirm": "StrongPass123",
  "first_name": "John",
  "last_name": "Doe",
  "company": "Pertamina",
  "phone": "081234567890"
}

Response 201:
{
  "message": "Signup berhasil",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@pertamina.com",
    "first_name": "John",
    "last_name": "Doe",
    "profile": {
      "role": "U",
      "department": "OTHER",
      "company": "Pertamina",
      "phone": "081234567890"
    },
    "date_joined": "2026-03-12T10:00:00Z"
  },
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer"
}
```

**Password Requirements:**
- ✅ Minimal 8 karakter
- ✅ Minimal 1 huruf besar (A-Z)
- ✅ Minimal 1 angka (0-9)

---

### 2. **Login** (POST)
```
POST /api/users/auth/login/
Content-Type: application/json

{
  "username": "john_doe",  // bisa juga pake email
  "password": "StrongPass123"
}

Response 200:
{
  "message": "Login berhasil",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@pertamina.com",
    "first_name": "John",
    "last_name": "Doe",
    "profile": {...},
    "date_joined": "2026-03-12T10:00:00Z"
  },
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer"
}
```

**Catatan:**
- Bisa login dengan **username** atau **email**
- Token access berlaku 24 jam
- Token refresh berlaku 7 hari

---

### 3. **Refresh Token** (POST)
```
POST /api/users/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response 200:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer"
}
```

---

### 4. **Logout** (POST)
```
POST /api/users/auth/logout/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Logout berhasil"
}
```

---

### 5. **Get Current User** (GET)
```
GET /api/users/me/
Authorization: Bearer <access_token>

Response 200:
{
  "id": 1,
  "username": "john_doe",
  "email": "john@pertamina.com",
  "first_name": "John",
  "last_name": "Doe",
  "profile": {
    "id": 1,
    "role": "U",
    "department": "OTHER",
    "company": "Pertamina",
    "phone": "081234567890",
    "is_verified": false
  },
  "date_joined": "2026-03-12T10:00:00Z"
}
```

---

### 6. **Update Profile** (PUT)
```
PUT /api/users/update_profile/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "company": "Pertamina",
  "phone": "081234567890"
}

Response 200:
{
  "id": 1,
  "username": "john_doe",
  "email": "john@pertamina.com",
  "first_name": "John",
  "last_name": "Doe",
  "profile": {...}
}
```

---

### 7. **Change Password** (POST)
```
POST /api/users/change_password/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "old_password": "OldPass123",
  "new_password": "NewPass456",
  "new_password_confirm": "NewPass456"
}

Response 200:
{
  "message": "Password berhasil diubah"
}
```

---

## 📝 Perubahan yang Dilakukan

### 1. **Management Command untuk Create Admin** ✅
- File: `apps/users/management/commands/create_admin.py`
- Fitur: Create admin user dengan validation lengkap
- Penggunaan: `python manage.py create_admin`

### 2. **Standalone Script untuk Create Admin** ✅
- File: `create_admin_user.py`
- Fitur: Script standalone tanpa memerlukan Django management
- Penggunaan: `python create_admin_user.py`

### 3. **Fix Signup Page** ✅
- **Sebelumnya:** Auto-login setelah signup
- **Sekarang:** Hanya buat user, redirect ke login page
- Alasan: Pisahkan proses register dan login

### 4. **Update Signup Template** ✅
- Tambah: Success message display
- Tambah: Link ke login page setelah signup
- Perbaikan: Form hanya ditampilkan jika belum signup

### 5. **Password Validation Improvement** ✅
- Standardisasi validation untuk semua endpoint
- Requirements: Min 8 char, 1 uppercase, 1 number

---

## 🧪 Panduan Testing

### Menggunakan cURL

#### 1. Test Sign Up
```bash
curl -X POST http://localhost:8000/api/users/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPass123",
    "password_confirm": "TestPass123",
    "first_name": "Test",
    "last_name": "User",
    "company": "Pertamina",
    "phone": "081234567890"
  }'
```

#### 2. Test Login
```bash
curl -X POST http://localhost:8000/api/users/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "TestPass123"
  }'
```

#### 3. Test Get Current User
```bash
curl -X GET http://localhost:8000/api/users/me/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### 4. Test Logout
```bash
curl -X POST http://localhost:8000/api/users/auth/logout/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### Menggunakan Postman

1. **Import Collection** (Opsional)
   - Buat new collection: "Chatbot Pertamina Auth"
   - Tambah variable: `base_url` = `http://localhost:8000/api`

2. **Test Sign Up**
   - Method: POST
   - URL: `{{base_url}}/users/auth/signup/`
   - Body: (Raw, JSON)

3. **Test Login**
   - Method: POST
   - URL: `{{base_url}}/users/auth/login/`
   - Body: (Raw, JSON)
   - Safe token ke environment variable: `token`

4. **Test Get Current User**
   - Method: GET
   - URL: `{{base_url}}/users/me/`
   - Header: `Authorization: Bearer {{token}}`

---

## 🔧 Troubleshooting

### Problem: "Username sudah digunakan"
**Solution:** Gunakan username yang belum terdaftar. Cek di database:
```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.filter(username='admin')
```

### Problem: "Email sudah terdaftar"
**Solution:** Gunakan email yang belum terdaftar:
```bash
>>> User.objects.filter(email='admin@pertamina.com')
```

### Problem: "Password tidak memenuhi requirement"
**Solution:** Pastikan password:
- ✅ Min 8 karakter
- ✅ Ada huruf besar (A-Z)
- ✅ Ada angka (0-9)

Contoh: `Admin123`, `StrongPass456`, `MyPassword789`

### Problem: "Module not found" saat run create_admin_user.py
**Solution:** Pastikan:
1. Berada di root directory project
2. Virtual environment sudah aktif
3. Update `sys.path.insert(0, ...)` path jika struktur berbeda

---

## 📊 User Roles

```
Role Choices:
- 'A' = Admin     (Full access)
- 'U' = User      (Regular user)
- 'S' = Support   (Support staff)
- 'M' = Manager   (Manager role)
```

Default role untuk signup: `'U'` (User)
Admin user dibuat dengan role: `'A'` (Admin)

---

## 🔐 Security Best Practices

1. ✅ **Password hashing** menggunakan Django's default hashing
2. ✅ **JWT tokens** untuk API authentication
3. ✅ **HTTPS** recommended untuk production
4. ✅ **Token expiration** (Access: 24h, Refresh: 7d)
5. ✅ **Password validation** (Min 8 char, 1 upper, 1 digit)

---

## 📞 Support

Untuk pertanyaan atau issues, silakan hubungi tim development.

---

**Last Updated:** March 12, 2026
**Status:** ✅ Ready for Production
