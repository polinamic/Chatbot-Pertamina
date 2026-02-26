# API Authentication Documentation

## Overview
Backend telah diintegrasikan dengan JWT-based authentication. Semua requests ke API yang memerlukan autentikasi harus menyertakan Bearer token dalam Authorization header.

## Authentication Endpoints

### 1. Signup (Register User)
**Endpoint:** `POST /api/v1/users/auth/signup/`

**Request Body:**
```json
{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "company": "Pertamina",
    "phone": "08123456789"
}
```

**Requirements:**
- Name: minimum 3 characters
- Email: valid email format, must be unique
- Password: minimum 8 characters, must contain uppercase letter and digit

**Response (201 Created):**
```json
{
    "message": "Signup berhasil",
    "user": {
        "user_id": "abc123def4",
        "name": "John Doe",
        "email": "john@example.com",
        "role": "U",
        "company": "Pertamina",
        "phone": "08123456789",
        "is_verified": false,
        "created_at": "2026-02-26T10:30:00Z"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_token_expires_in": 86400,
    "token_type": "Bearer"
}
```

---

### 2. Login
**Endpoint:** `POST /api/v1/users/auth/login/`

**Request Body:**
```json
{
    "email": "john@example.com",
    "password": "SecurePass123"
}
```

**Response (200 OK):**
```json
{
    "message": "Login berhasil",
    "user": {
        "user_id": "abc123def4",
        "name": "John Doe",
        "email": "john@example.com",
        "role": "U",
        "company": "Pertamina",
        "phone": "08123456789",
        "is_verified": false,
        "created_at": "2026-02-26T10:30:00Z"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_token_expires_in": 86400,
    "token_type": "Bearer"
}
```

**Error Response (400/401):**
```json
{
    "success": false,
    "error": {
        "email": ["Email atau password salah"]
    },
    "status_code": 400
}
```

---

### 3. Refresh Token
**Endpoint:** `POST /api/v1/users/auth/refresh/`

**Request Body:**
```json
{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_token_expires_in": 86400,
    "token_type": "Bearer"
}
```

---

### 4. Logout (Optional)
**Endpoint:** `POST /api/v1/users/auth/logout/`

**Headers Required:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "message": "Logout berhasil"
}
```

---

## User Profile Endpoints

### 5. Get Current User Profile
**Endpoint:** `GET /api/v1/users/me/`

**Headers Required:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "user_id": "abc123def4",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "U",
    "company": "Pertamina",
    "phone": "08123456789",
    "is_verified": false,
    "created_at": "2026-02-26T10:30:00Z"
}
```

---

### 6. Update User Profile
**Endpoint:** `PUT /api/v1/users/update_profile/`

**Headers Required:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
    "name": "John Updated",
    "phone": "08987654321",
    "company": "Pertamina Updated"
}
```

**Response (200 OK):**
```json
{
    "name": "John Updated",
    "phone": "08987654321",
    "company": "Pertamina Updated"
}
```

---

### 7. Change Password
**Endpoint:** `POST /api/v1/users/change_password/`

**Headers Required:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
    "old_password": "SecurePass123",
    "new_password": "NewSecurePass456",
    "new_password_confirm": "NewSecurePass456"
}
```

**Response (200 OK):**
```json
{
    "message": "Password berhasil diubah"
}
```

---

## Token Usage

### In HTTP Headers:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Expiration:
- **Access Token:** 24 hours
- **Refresh Token:** 7 days

### Token Payload:
```json
{
    "user_id": "abc123def4",
    "email": "john@example.com",
    "type": "access",
    "exp": 1234567890,
    "iat": 1234564290
}
```

---

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    user_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(128),
    email VARCHAR(128),
    password_hash VARCHAR(255),
    role CHAR(1),
    company VARCHAR(100),
    phone VARCHAR(15),
    is_active BOOLEAN,
    is_verified BOOLEAN,
    last_login TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Other Related Tables
- `llm_config` - LLM configuration
- `conversation` - Chat conversations
- `message` - Chat messages
- `document` - Documents for RAG
- `document_chunk` - Document chunks with embeddings
- `retrieval_log` - Document retrieval logs
- `escalation_log` - Escalation logs
- `activity_log` - User activity logs

---

## Security Notes

1. **Password Hashing:** Passwords are hashed using Django's default PBKDF2 algorithm
2. **Token Security:** Store refresh tokens securely (preferably in httpOnly cookies)
3. **HTTPS:** Always use HTTPS in production
4. **CSRF Protection:** CSRF tokens are required for state-changing operations
5. **Rate Limiting:** Implement rate limiting on login/signup endpoints (optional)

---

## Testing with cURL

### Signup:
```bash
curl -X POST http://localhost:8000/api/v1/users/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "company": "Pertamina"
  }'
```

### Login:
```bash
curl -X POST http://localhost:8000/api/v1/users/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123"
  }'
```

### Get Current User:
```bash
curl -X GET http://localhost:8000/api/v1/users/me/ \
  -H "Authorization: Bearer <access_token>"
```

---

## Middleware

### JWT Authentication Middleware
- Validates JWT tokens on every request
- Extracts user_id from token claims
- Returns 401 Unauthorized for invalid/expired tokens

### CORS Middleware
- Handles cross-origin requests
- Sets appropriate CORS headers

### Activity Log Middleware
- Logs user login/logout events
- Logs API usage for analytics

---

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `TOKEN_EXPIRED` | 401 | JWT token has expired |
| `INVALID_TOKEN` | 401 | JWT token is invalid |
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `SERVER_ERROR` | 500 | Internal server error |
