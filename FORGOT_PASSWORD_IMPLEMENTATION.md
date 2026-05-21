# Forgot Password Feature - Implementation Guide

## Overview

A complete **Forgot Password** feature has been implemented for your Django chatbot application. This guide covers setup, configuration, and usage.

## What's Been Implemented

### 1. **Database Model** (`PasswordResetToken`)
- Stores secure password reset tokens
- Tokens are hashed in the database (not plaintext)
- Automatic expiry (15 minutes default)
- One active token per user at a time
- Tracks token usage and timestamps

**Location:** [apps/users/models.py](apps/users/models.py#L100-L200)

**Key Methods:**
- `generate_token()` - Creates cryptographically secure random token
- `hash_token(token)` - Hashes token using Django's password hasher
- `is_valid()` - Validates token (not expired and not used)
- `create_for_user(user, expiry_minutes=15)` - Creates token for user
- `get_user_from_token(token)` - Validates token and returns user
- `mark_as_used()` - Marks token as consumed

### 2. **Email Service** (`EmailService`)
- Sends professional HTML emails
- Password reset email with reset link
- Password changed confirmation email
- Welcome email for new users
- Graceful error handling with logging

**Location:** [apps/users/email_service.py](apps/users/email_service.py)

**Methods:**
- `send_password_reset_email(email, reset_link, expiry_minutes)`
- `send_password_changed_confirmation_email(email)`
- `send_welcome_email(email, username)`

### 3. **Email Templates**
Professional HTML email templates with styling:
- [Password Reset Email](apps/users/templates/emails/password_reset.html)
- [Password Changed Email](apps/users/templates/emails/password_changed.html)
- [Welcome Email](apps/users/templates/emails/welcome.html)

### 4. **API Endpoints**

#### Forgot Password Endpoint
```
POST /api/auth/forgot-password/
Content-Type: application/json

{
  "email": "user@pertamina.com"
}

Response: 200 OK
{
  "message": "Jika email terdaftar, link reset password telah dikirim ke email Anda...",
  "code": "PASSWORD_RESET_EMAIL_SENT"
}
```

**Features:**
- Generic success message (doesn't reveal if email exists)
- Rate limiting capable (not implemented by default)
- Invalidates previous tokens
- Sends email with reset link
- Logs activity for security audit

**Location:** [apps/users/views.py - ForgotPasswordView](apps/users/views.py#L630-L700)

#### Reset Password Endpoint
```
POST /api/auth/reset-password/
Content-Type: application/json

{
  "token": "reset-token-from-email",
  "new_password": "NewPassword123",
  "new_password_confirm": "NewPassword123"
}

Response: 200 OK
{
  "message": "Password berhasil diubah. Silakan login dengan password baru Anda.",
  "code": "PASSWORD_RESET_SUCCESS"
}
```

**Features:**
- Token validation (exists, not expired, not used)
- Password strength validation
- Automatic token invalidation after use
- Confirmation email sent
- Activity logging

**Location:** [apps/users/views.py - ResetPasswordView](apps/users/views.py#L700-L800)

### 5. **Web Pages**

#### Forgot Password Page
- URL: `/auth/forgot-password/`
- Clean, responsive form
- Dark mode support
- Email validation
- Security info box
- Link to login/signup

**Location:** [apps/users/templates/users/forgot_password.html](apps/users/templates/users/forgot_password.html)

#### Reset Password Page
- URL: `/auth/reset-password/?token=xxxxx`
- Token validation before showing form
- Password strength requirements
- Real-time password validation
- Dark mode support
- Error messages for expired/used tokens

**Location:** [apps/users/templates/users/reset_password.html](apps/users/templates/users/reset_password.html)

### 6. **Serializers**
- `ForgotPasswordSerializer` - Validates email input
- `ResetPasswordSerializer` - Validates token and new password

**Location:** [apps/users/serializers.py](apps/users/serializers.py#L260-L310)

### 7. **Database Migration**
- Migration file: [0004_passwordresettoken.py](apps/users/migrations/0004_passwordresettoken.py)
- Creates `PasswordResetToken` table
- Adds indexes for performance

---

## Setup Instructions

### 1. **Apply Database Migration**

```bash
python manage.py migrate
```

This creates the `PasswordResetToken` table.

### 2. **Configure Email Settings**

Edit `.env` file or set environment variables:

#### For Development (Console Backend - Prints to Console)
```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@sitichatbot.pertamina.com
FRONTEND_URL=http://localhost:3000
```

#### For Production (Gmail SMTP)
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
DEFAULT_FROM_EMAIL=noreply@sitichatbot.pertamina.com
FRONTEND_URL=https://yourdomain.com
```

**Note:** For Gmail, use an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

#### For SendGrid
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@sitichatbot.pertamina.com
```

### 3. **Update FRONTEND_URL**

The password reset email contains a link like:
```
https://yourdomain.com/auth/reset-password?token=xxxxx
```

Make sure `FRONTEND_URL` points to your frontend domain. Update [config/settings.py](config/settings.py) or `.env`:

```
FRONTEND_URL=https://yourdomain.com  # for production
FRONTEND_URL=http://localhost:3000   # for development
```

### 4. **Test Email Configuration**

Test email sending:
```bash
python manage.py shell
```

```python
from apps.users.email_service import EmailService

# Test email
EmailService.send_password_reset_email(
    'test@example.com',
    'http://localhost:3000/auth/reset-password?token=test-token-123',
    token_expiry_minutes=15
)
```

---

## API Usage Examples

### Frontend Example (JavaScript/React)

#### Forgot Password
```javascript
// User submits forgot password form
const email = 'user@pertamina.com';

fetch('http://localhost:8000/api/auth/forgot-password/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ email })
})
.then(res => res.json())
.then(data => {
  if (data.code === 'PASSWORD_RESET_EMAIL_SENT') {
    alert('Link reset password telah dikirim ke email Anda');
    // Redirect to login
  } else {
    alert('Terjadi kesalahan: ' + data.error);
  }
});
```

#### Reset Password
```javascript
// User comes from email link with token in URL
const token = new URLSearchParams(window.location.search).get('token');
const newPassword = 'NewPassword123';
const confirmPassword = 'NewPassword123';

fetch('http://localhost:8000/api/auth/reset-password/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    token,
    new_password: newPassword,
    new_password_confirm: confirmPassword
  })
})
.then(res => res.json())
.then(data => {
  if (data.code === 'PASSWORD_RESET_SUCCESS') {
    alert('Password berhasil diubah');
    // Redirect to login
  } else {
    alert('Error: ' + (data.error || data.message));
  }
});
```

### cURL Examples

#### Forgot Password
```bash
curl -X POST http://localhost:8000/api/auth/forgot-password/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@pertamina.com"}'
```

#### Reset Password
```bash
curl -X POST http://localhost:8000/api/auth/reset-password/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "reset-token-from-email",
    "new_password": "NewPassword123",
    "new_password_confirm": "NewPassword123"
  }'
```

---

## Security Features

### ✅ Implemented
1. **Token Hashing** - Tokens stored as hashes, not plaintext
2. **Cryptographic Randomness** - Uses `secrets.token_urlsafe()` for token generation
3. **Automatic Expiry** - Tokens expire after 15 minutes
4. **One-Time Use** - Tokens marked as used after first use
5. **One Active Token Per User** - Previous tokens invalidated when new request made
6. **Generic Success Messages** - Doesn't reveal if email exists (prevents user enumeration)
7. **Password Strength Validation** - Enforces:
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one digit
8. **Activity Logging** - All password reset attempts logged for audit trail
9. **Rate Limiting Ready** - Can be added via middleware

### 🔐 Best Practices Implemented
- No sensitive data in logs
- Proper error messages to users
- Email validation before sending
- Token validation before password update
- Secure password hashing (Django's default)
- CSRF protection on web forms
- Dark mode support for consistency

### ⚠️ Optional Enhancements

#### Rate Limiting
Add Django-ratelimit:
```bash
pip install django-ratelimit
```

Then in [apps/users/views.py](apps/users/views.py):
```python
from django_ratelimit.decorators import ratelimit

class ForgotPasswordView(views.APIView):
    @ratelimit(key='ip', rate='5/h', method='POST')
    def post(self, request):
        # ...
```

#### Email Queue (Celery)
For better performance, send emails asynchronously:
```python
# In ForgotPasswordView
from celery import shared_task

@shared_task
def send_reset_email_task(email, reset_link):
    EmailService.send_password_reset_email(email, reset_link)

# In view
send_reset_email_task.delay(user.email, reset_link)
```

---

## Testing

### Unit Tests

Create [tests/test_forgot_password.py](tests/test_forgot_password.py):

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.users.models import PasswordResetToken

class ForgotPasswordTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123'
        )

    def test_forgot_password_endpoint(self):
        """Test forgot password API endpoint"""
        response = self.client.post('/api/auth/forgot-password/', {
            'email': 'test@example.com'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 'PASSWORD_RESET_EMAIL_SENT')
        
        # Verify token was created
        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user).exists()
        )

    def test_reset_password_with_valid_token(self):
        """Test password reset with valid token"""
        # Create token
        plain_token, reset_token = PasswordResetToken.create_for_user(self.user)
        
        # Reset password
        response = self.client.post('/api/auth/reset-password/', {
            'token': plain_token,
            'new_password': 'NewPassword456',
            'new_password_confirm': 'NewPassword456'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 'PASSWORD_RESET_SUCCESS')
        
        # Verify token is marked as used
        reset_token.refresh_from_db()
        self.assertTrue(reset_token.is_used)
        
        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPassword456'))

    def test_reset_password_with_expired_token(self):
        """Test password reset with expired token"""
        from datetime import timedelta
        from django.utils import timezone
        
        # Create expired token
        plain_token, reset_token = PasswordResetToken.create_for_user(self.user)
        reset_token.expires_at = timezone.now() - timedelta(minutes=1)
        reset_token.save()
        
        # Try to reset password
        response = self.client.post('/api/auth/reset-password/', {
            'token': plain_token,
            'new_password': 'NewPassword456',
            'new_password_confirm': 'NewPassword456'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'TOKEN_EXPIRED')
```

Run tests:
```bash
python manage.py test tests.test_forgot_password
```

---

## File Structure

```
apps/users/
├── models.py                      # PasswordResetToken model
├── serializers.py                 # ForgotPasswordSerializer, ResetPasswordSerializer
├── views.py                       # ForgotPasswordView, ResetPasswordView
├── email_service.py               # EmailService for sending emails
├── urls.py                        # Updated with forgot/reset URLs
├── templates/
│   ├── users/
│   │   ├── forgot_password.html   # Forgot password form
│   │   └── reset_password.html    # Reset password form
│   └── emails/
│       ├── password_reset.html    # Reset email template
│       ├── password_changed.html  # Confirmation email template
│       └── welcome.html           # Welcome email template
└── migrations/
    └── 0004_passwordresettoken.py # Database migration

config/
└── settings.py                    # Email configuration settings

.env.example                       # Environment variable examples
```

---

## Troubleshooting

### Issue: Emails not sending in development
**Solution:** Ensure `EMAIL_BACKEND` is set correctly:
```
# In .env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```
Emails will print to console. Check Django logs.

### Issue: "Token invalid or expired" in reset page
**Possible causes:**
1. Token has been used already
2. Token has expired (older than 15 minutes)
3. Token was never created for this email

**Solution:** User must request a new password reset link.

### Issue: Gmail SMTP not working
**Solution:** 
1. Use an [App Password](https://myaccount.google.com/apppasswords), not regular password
2. Make sure 2FA is enabled on your Google account
3. Set `EMAIL_USE_TLS=True` and `EMAIL_PORT=587`

### Issue: No token received after password reset request
**Possible causes:**
1. User doesn't exist with that email
2. Email service is not configured
3. Email goes to spam folder

**Solution:**
1. Check user exists in database
2. Verify `EMAIL_BACKEND` and SMTP settings
3. Check email spam/junk folder
4. Check Django logs for errors

---

## Database Administration

### View Reset Tokens in Admin Panel

1. Go to Django Admin: `http://localhost:8000/admin`
2. Look for "Password Reset Tokens" section
3. Can view:
   - Token creation time
   - Expiry time
   - Whether token was used
   - Associated user

### Manually Invalidate a Token

```python
python manage.py shell

from apps.users.models import PasswordResetToken

# Invalidate specific user's tokens
PasswordResetToken.objects.filter(user_id=1, is_used=False).delete()

# Or mark as used
token = PasswordResetToken.objects.get(id=1)
token.mark_as_used()
```

---

## Production Checklist

- [ ] Email backend configured (not console backend)
- [ ] SMTP credentials set securely in environment variables
- [ ] `FRONTEND_URL` points to production domain
- [ ] HTTPS enabled on production
- [ ] Rate limiting configured (optional)
- [ ] Email service tested
- [ ] Database migration applied
- [ ] Error logging configured
- [ ] CORS settings updated for production
- [ ] Security headers configured

---

## URLs Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/forgot-password/` | POST | Request password reset |
| `/api/auth/reset-password/` | POST | Reset password with token |
| `/auth/forgot-password/` | GET/POST | Forgot password web page |
| `/auth/reset-password/` | GET/POST | Reset password web page |

---

## Next Steps

1. **Apply migration:** `python manage.py migrate`
2. **Configure email:** Update `.env` with your email provider
3. **Test emails:** Run the Django shell test
4. **Add to frontend:** Update your React/Vue/etc app with forgot password links
5. **Optional:** Add rate limiting and email queuing

For questions, check the implementation in:
- Models: [apps/users/models.py](apps/users/models.py)
- Views: [apps/users/views.py](apps/users/views.py)
- Email: [apps/users/email_service.py](apps/users/email_service.py)

---

**Last Updated:** 2024
**Version:** 1.0.0
