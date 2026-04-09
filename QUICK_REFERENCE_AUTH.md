## 🚀 Quick Reference Guide - Authentication Refactoring

### ✅ What Changed & Why

| Feature | Before | After | File |
|---------|--------|-------|------|
| **Signup** | Auto-login | Redirect to login | views.py |
| **Chat Protection** | No auth check | Requires login | views.py |
| **User Settings** | Not implemented | DB-backed, per-user | models.py, views.py |
| **Profile Edit** | Not implemented | Full profile page | views.py, templates |
| **Error Messages** | Basic | Clear & helpful | templates |

---

### 📋 New Routes Added

```
GET  /auth/profile/           → View/edit user profile
POST /auth/profile/          → Save profile changes

GET  /auth/settings/         → User-specific settings
POST /auth/settings/         → Save settings per user
```

---

### 🔑 Key Code Snippets

#### **1. Auto-Create Profile & Settings**
```python
# signals.py
@receiver(post_save, sender=User)
def create_user_profile_and_settings(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        UserSettings.objects.get_or_create(
            user=instance,
            defaults={'theme': 'auto', 'language': 'id', ...}
        )
```

#### **2. Auth Decorator for Views**
```python
# decorators.py
def login_required_redirect(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse('users:login'))
        return view_func(request, *args, **kwargs)
    return wrapped_view

# Usage in views
@login_required_redirect
def profile_page(request):
    ...
```

#### **3. Fixed Signup - No Auto-Login**
```python
# views.py - signup_page()
# Create user
user = User.objects.create_user(username, email, password)

# Log activity
ActivityLog.objects.create(action='CREATE', ...)

# ✅ FIX: Don't auto-login! Instead show success + link to login
return render(request, 'users/signup.html', {
    'success': 'Akun berhasil dibuat! Silakan login...',
    'show_login_redirect': True
})
```

#### **4. Protected Chat Page**
```python
# chatbot/views.py
def chat_page(request):
    @login_required_redirect
    def _chat_page(request):
        user = request.user
        conversations = Conversation.objects.filter(user=user)
        return render(request, 'chatbot/chat.html', {...})
    return _chat_page(request)
```

#### **5. UserSettings Model (Per-User)**
```python
# models.py
class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                                related_name='settings')
    theme = models.CharField(choices=[...], default='auto')
    language = models.CharField(choices=[...], default='id')
    enable_notifications = models.BooleanField(default=True)
    # ... more fields
    
# Each user has a unique settings record!
# Query: user.settings.theme
```

---

### 🗄️ Database Relationships

```
User (id=1)
├── UserProfile (linked OneToOne)
│   └── role, department, company, phone, bio
├── UserSettings (linked OneToOne) ← USER-SPECIFIC!
│   └── theme, language, notifications, privacy, etc.
├── Conversation (linked ForeignKey) × Many
│   └── Message (linked ForeignKey) × Many
└── ActivityLog (linked by user_id) × Many
    └── records of signup/login/logout/etc
```

**Key**: `user_id` is the foreign key linking all user data.

---

### 🧪 Testing Checklist

- [ ] User signs up → NOT auto-logged in
- [ ] User sees success message with login link
- [ ] Must login manually to access chat
- [ ] Chat redirects to login if not authenticated
- [ ] Profile page loads user data
- [ ] Profile updates saved to database
- [ ] Settings page shows user preferences
- [ ] Settings per-user (not global)
- [ ] Different users have different settings
- [ ] ActivityLog records events
- [ ] UserProfile auto-created on signup
- [ ] UserSettings auto-created on signup

---

### 🐛 Common Issues & Fixes

**Issue**: "User not logged in after signup"
- **Fix**: This is correct! Users must login manually now.

**Issue**: "Can't access chat page without login"
- **Fix**: This is correct! Auth protection is working.

**Issue**: "Settings show other user's data"
- **Fix**: Check the user_id foreign key in database
  ```sql
  SELECT * FROM users_usersettings WHERE user_id = ?
  ```

**Issue**: "Profile not created for new user"
- **Fix**: Check if signals.py is registered in apps.py
  ```python
  # apps.py
  def ready(self):
      import apps.users.signals
  ```

---

### 📊 What Gets Stored Where

```
Login Credentials
├── User.username ..................... Django Auth
├── User.password .................... PBKDF2 hashed
└── User.last_login .................. Timestamp

User Profile
├── UserProfile.role ................. A/U/S/M
├── UserProfile.department ........... IT/HR/OPS/FIN
└── UserProfile.phone, bio, company .. User info

User Settings (DATABASE-BACKED!)
├── UserSettings.theme .............. light/dark/auto
├── UserSettings.language ........... id/en
├── UserSettings.enable_notifications  bool
└── UserSettings.is_profile_public ... bool

Session State
├── Django Session .................. In database
└── CSRF Token ...................... Security
```

---

### 🔐 Security Checklist

✅ Password hashing: PBKDF2 (Django default)
✅ Session security: Secure cookies, CSRF tokens
✅ Access control: Login required on protected pages
✅ Data isolation: User can only access own data
✅ Audit logging: All auth events logged
✅ No hardcoded credentials
✅ HTTPS ready (SESSION_COOKIE_SECURE=True in prod)

---

### 📱 Frontend Integration

**Update base.html to add links:**
```html
<!-- If user logged in, show profile/settings links -->
{% if user.is_authenticated %}
    <a href="{% url 'users:profile' %}">👤 Profil</a>
    <a href="{% url 'users:settings' %}">⚙️ Pengaturan</a>
    <a href="{% url 'users:logout' %}">🚪 Logout</a>
{% else %}
    <a href="{% url 'users:login' %}">🔐 Login</a>
    <a href="{% url 'users:signup' %}">📝 Signup</a>
{% endif %}
```

---

### 🎯 Implementation Summary

| Requirement | Status | Location |
|------------|--------|----------|
| Signup doesn't auto-login | ✅ | views.py line ~366 |
| Login requires credentials | ✅ | views.py LoginView |
| Chat page protected | ✅ | chatbot/views.py |
| Profile page exists | ✅ | views.py, templates/profile.html |
| Settings per-user | ✅ | models.py UserSettings |
| Settings in database | ✅ | models.py, migrations |
| User isolation | ✅ | model relationships |
| Secure hashing | ✅ | Django default PBKDF2 |
| Session management | ✅ | Django SessionMiddleware |
| Audit logging | ✅ | ActivityLog model |

---

### 🚀 Deployment Checklist

Before going to production:

- [ ] Set `DEBUG = False` in settings.py
- [ ] Set `SECRET_KEY` to random value (not default)
- [ ] Set `ALLOWED_HOSTS` to your domain
- [ ] Set `SESSION_COOKIE_SECURE = True` (HTTPS only)
- [ ] Set `SESSION_COOKIE_HTTPONLY = True`
- [ ] Set `CSRF_COOKIE_SECURE = True`
- [ ] Run `python manage.py collectstatic`
- [ ] Review `config/settings.py` security settings
- [ ] Set up HTTPS/SSL certificate
- [ ] Test login/logout flow end-to-end
- [ ] Verify user data isolation works
- [ ] Check ActivityLog is recording events

---

**Last Updated**: April 2026
**Status**: ✅ Complete & Ready for Testing
