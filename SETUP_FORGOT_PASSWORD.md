# Quick Setup Guide - Forgot Password Feature

## ⚡ 5-Minute Setup

### Step 1: Apply Database Migration
```bash
python manage.py migrate
```

### Step 2: Configure Email (Choose One)

#### Option A: Development (Console - Prints to Console)
Add to `.env`:
```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
FRONTEND_URL=http://localhost:3000
```

#### Option B: Production (Gmail)
1. Get [Gmail App Password](https://myaccount.google.com/apppasswords)
2. Add to `.env`:
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
FRONTEND_URL=https://yourdomain.com
```

#### Option C: Production (SendGrid)
1. Get SendGrid API key
2. Add to `.env`:
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.your-api-key
FRONTEND_URL=https://yourdomain.com
```

### Step 3: Test Email
```bash
python manage.py shell
```
```python
from apps.users.email_service import EmailService
EmailService.send_password_reset_email(
    'test@example.com',
    'http://localhost:3000/auth/reset-password?token=test123',
    token_expiry_minutes=15
)
```

### Step 4: Run Server
```bash
python manage.py runserver
```

### Step 5: Test URLs
- Forgot Password Page: http://localhost:8000/auth/forgot-password/
- API Endpoint: POST http://localhost:8000/api/auth/forgot-password/

---

## ✨ What's New

### Web Pages
- **Forgot Password:** `/auth/forgot-password/`
  - Enter email
  - Get reset link sent to email
  - Generic success message (security)

- **Reset Password:** `/auth/reset-password/?token=xxxxx`
  - Set new password
  - Real-time validation
  - Automatic token validation

### API Endpoints
- `POST /api/auth/forgot-password/`
  - Input: `{"email": "user@example.com"}`
  - Returns: Generic success message

- `POST /api/auth/reset-password/`
  - Input: `{"token": "xxx", "new_password": "xxx", "new_password_confirm": "xxx"}`
  - Returns: Success or error message

### Email Templates
- Password reset email with reset link
- Password changed confirmation email
- Professional HTML styling

---

## 🔐 Security Features Built-In

✅ Tokens hashed in database (not plaintext)  
✅ Cryptographically secure token generation  
✅ 15-minute expiry  
✅ One-time use only  
✅ One active token per user  
✅ Generic success messages (no email enumeration)  
✅ Password strength validation  
✅ Activity logging  

---

## 📁 Files Added/Modified

**New Files:**
- `apps/users/models.py` - Added `PasswordResetToken` model
- `apps/users/email_service.py` - Email sending utility
- `apps/users/templates/emails/password_reset.html` - Email template
- `apps/users/templates/emails/password_changed.html` - Confirmation email
- `apps/users/templates/users/forgot_password.html` - Forgot password page
- `apps/users/templates/users/reset_password.html` - Reset password page
- `apps/users/migrations/0004_passwordresettoken.py` - Database migration

**Modified Files:**
- `apps/users/serializers.py` - Added serializers
- `apps/users/views.py` - Added API views
- `apps/users/urls.py` - Added new URL routes
- `config/settings.py` - Added email configuration
- `.env.example` - Added email examples

---

## 🧪 Test It

### Web Form Test
1. Go to http://localhost:8000/auth/forgot-password/
2. Enter your test user's email
3. Check console (if using console backend) or email
4. Click reset link
5. Set new password
6. Login with new password

### API Test
```bash
# Step 1: Request password reset
curl -X POST http://localhost:8000/api/auth/forgot-password/ \
  -H "Content-Type: application/json" \
  -d '{"email": "testuser@example.com"}'

# Response should show: PASSWORD_RESET_EMAIL_SENT
```

---

## 🆘 Troubleshooting

**Q: Email not sending?**
- A: Check `EMAIL_BACKEND` is correct and email config is set

**Q: "Token invalid" on reset page?**
- A: Token may have expired (15 min) or already been used

**Q: How do I change token expiry time?**
- A: Edit view: `PasswordResetToken.create_for_user(user, expiry_minutes=30)`

**Q: Can I customize email template?**
- A: Yes! Edit HTML files in `apps/users/templates/emails/`

---

## 📚 Full Documentation

See [FORGOT_PASSWORD_IMPLEMENTATION.md](FORGOT_PASSWORD_IMPLEMENTATION.md) for complete documentation including:
- Database schema details
- API response codes
- Email configuration options
- Advanced setup (rate limiting, email queuing)
- Testing examples
- Production checklist

---

## 💡 Quick Integration Tips

### For React/Vue Frontend
```javascript
// Forgot password
const response = await fetch('/api/auth/forgot-password/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@example.com' })
});

// Reset password
const response = await fetch('/api/auth/reset-password/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    token: urlParams.get('token'),
    new_password: password,
    new_password_confirm: confirmPassword
  })
});
```

### Link in Email Sent To
User receives email with link like:
```
https://yourdomain.com/auth/reset-password?token=abcdef123456
```

Change domain by updating `FRONTEND_URL` in `.env`

---

## ✅ Next Steps

1. ✅ Apply migration: `python manage.py migrate`
2. ✅ Configure email in `.env`
3. ✅ Test email sending
4. ✅ Test web forms at `/auth/forgot-password/`
5. ✅ Test API endpoints
6. ✅ Integrate into your frontend
7. ✅ Deploy to production with email service

---

**Ready to use!** 🎉
