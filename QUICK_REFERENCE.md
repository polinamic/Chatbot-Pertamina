# 🚀 QUICK REFERENCE - Auth Backend

## Create Admin User

### Method 1: Management Command (Interactive)
```bash
python manage.py create_admin
```

### Method 2: Standalone Script
```bash
python create_admin_user.py
```

### Method 3: Non-Interactive Command
```bash
python manage.py create_admin \
  --username admin \
  --email admin@pertamina.com \
  --password Admin123! \
  --firstname Admin \
  --lastname User
```

---

## Authentication Flow

```
1. SIGNUP
   POST /api/users/auth/signup/
   → User created + Tokens returned
   → User NOT auto-logged-in (must login separately)

2. LOGIN
   POST /api/users/auth/login/
   → Tokens returned (access + refresh)
   → Use access token for authenticated requests

3. USE TOKEN
   GET /api/users/me/
   Header: Authorization: Bearer <access_token>

4. REFRESH TOKEN
   POST /api/users/auth/refresh/
   Body: { "refresh_token": "..." }

5. LOGOUT
   POST /api/users/auth/logout/
   Header: Authorization: Bearer <access_token>
```

---

## API Endpoints Quick List

| Endpoint | Method | Auth | 200 Response |
|----------|--------|------|--------------|
| `/api/users/auth/signup/` | POST | ❌ | User + tokens |
| `/api/users/auth/login/` | POST | ❌ | User + tokens |
| `/api/users/auth/refresh/` | POST | ❌ | New tokens |
| `/api/users/auth/logout/` | POST | ✅ | OK message |
| `/api/users/me/` | GET | ✅ | User data |
| `/api/users/update_profile/` | PUT | ✅ | Updated user |
| `/api/users/change_password/` | POST | ✅ | OK message |

---

## Password Requirements

```
✅ Minimum 8 characters
✅ At least 1 uppercase letter (A-Z)
✅ At least 1 number (0-9)

❌ Examples (INVALID):
   - password123 (no uppercase)
   - PASSWORD (no number)
   - Pass1 (too short)

✅ Examples (VALID):
   - Admin123
   - StrongPass456
   - MyPassword789
```

---

## cURL Examples

### Signup
```bash
curl -X POST http://localhost:8000/api/users/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "email": "john@example.com",
    "password": "StrongPass123",
    "password_confirm": "StrongPass123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/users/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "password": "StrongPass123"
  }'
```

### Get Current User
```bash
curl http://localhost:8000/api/users/me/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Logout
```bash
curl -X POST http://localhost:8000/api/users/auth/logout/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Test Everything
```bash
python test_auth_backend.py
```

---

## Token Info

**Access Token:**
- Duration: 24 hours
- Use: API requests
- Format: `Authorization: Bearer <token>`

**Refresh Token:**
- Duration: 7 days
- Use: Get new access token
- Endpoint: `/api/users/auth/refresh/`

---

## Files Modified/Created

✨ **NEW Files:**
- `create_admin_user.py` - Standalone admin creator
- `test_auth_backend.py` - Test suite
- `AUTH_BACKEND_GUIDE.md` - Full documentation
- `PERBAIKAN_AUTH_SUMMARY.md` - Change summary
- `apps/users/management/commands/create_admin.py` - Django command

🔧 **MODIFIED Files:**
- `apps/users/views.py` - Fixed signup_page (no auto-login)
- `apps/users/templates/users/signup.html` - Added success message

---

## Roles Available

```
'A' = Admin     (Full access)
'U' = User      (Regular user, default)
'S' = Support   (Support staff)
'M' = Manager   (Manager role)
```

Admin users created via management command get role 'A'

---

## Common Issues

**Q: "Username sudah digunakan"**
A: Use different username

**Q: "Password tidak memenuhi requirement"**
A: Use at least 8 chars with 1 uppercase + 1 number

**Q: "Cannot find module"**
A: Run `pip install -r requirements.txt`

**Q: "Admin creation fails"**
A: Run `python manage.py migrate` first

---

## Documentation Files

- 📖 `AUTH_BACKEND_GUIDE.md` - Complete API reference
- 📋 `PERBAIKAN_AUTH_SUMMARY.md` - Detailed change log
- 📄 `QUICK_REFERENCE.md` - This file

---

## Next Steps

1. ✅ Create admin user
2. ✅ Test endpoints with `test_auth_backend.py`
3. ✅ Read `AUTH_BACKEND_GUIDE.md` for full docs
4. ✅ Implement frontend login/signup forms
5. ✅ Connect frontend to API endpoints

---

**Last Updated:** March 12, 2026
**Status:** ✅ Ready to Use
