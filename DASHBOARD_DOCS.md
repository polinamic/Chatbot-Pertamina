# Admin Dashboard Documentation

## Akses Dashboard

Admin dashboard dapat diakses di:
```
http://localhost:8000/dashboard/
```

**Requirements:**
- User harus login
- User harus memiliki status `is_staff=True` atau `is_superuser=True`

## Menu Dashboard

### 1. **Dashboard Home** (`/dashboard/`)
Menampilkan overview utama dengan:
- **Statistics Cards:**
  - Total Users
  - Total Conversations
  - Total Messages
  - Total Documents
  - Statistics untuk hari ini
  - Activity 7 hari terakhir

- **Charts & Data:**
  - 7-Day Activity Chart (visualisasi bar chart)
  - Recent Conversations (10 conversation terbaru)
  - Top Conversations by Messages (5 conversation dengan messages terbanyak)

### 2. **Conversations Management** (`/dashboard/conversations/`)
Mengelola semua conversations dengan fitur:
- **Filter:**
  - All Status
  - Active (aktif)
  - Archived (diarsipkan)

- **Table Display:**
  - Title
  - User
  - Message count
  - Status (Active/Archived)
  - Created date
  - Updated date

- **Pagination:** 20 items per halaman

### 3. **Users Management** (`/dashboard/users/`)
Mengelola user sistem dengan fitur:
- **Filter:**
  - All Roles
  - Admin
  - Staff
  - Users (regular users)

- **Table Display:**
  - Username
  - Email
  - Role (Admin/Staff/User)
  - Number of conversations
  - Number of messages
  - Joined date
  - Last login

- **Pagination:** 20 items per halaman

### 4. **Documents Management** (`/dashboard/documents/`)
Mengelola semua documents yang di-ingest dengan fitur:
- **Filter:**
  - All Status
  - Processed
  - Pending

- **Table Display:**
  - File name
  - Uploaded by
  - File size (dalam B, KB, MB)
  - Status (Processed/Pending)
  - Created date

- **Pagination:** 20 items per halaman

### 5. **Analytics & Reports** (`/dashboard/analytics/`)
Analitik mendalam dengan fitur:
- **Period Filter:**
  - Last 7 days
  - Last 30 days
  - Last 90 days
  - Last year

- **Metrics:**
  - Average Messages per Conversation
  - Conversations Trend (chart by date)
  - Top 10 Users by Conversations (dengan ranking 🥇🥈🥉)

## API Endpoints

### Statistik Real-time
```
GET /dashboard/api/stats/
```
Response:
```json
{
  "status": "success",
  "data": {
    "total_users": 100,
    "total_conversations": 250,
    "total_messages": 5000,
    "total_documents": 50,
    "conversations_today": 10,
    "messages_today": 150
  }
}
```

## Design & Features

### Professional Features:
✅ **Responsive Design** - Works on desktop, tablet, mobile
✅ **Dark Mode Support** - Automatic dark mode detection
✅ **Real-time Statistics** - Live data dari database
✅ **Pagination** - Navigasi mudah untuk data besar
✅ **Filters & Search** - Filter berdasarkan status/role
✅ **Modern UI** - Bootstrap Icons, smooth transitions
✅ **Pertamina Branding** - Warna brand Pertamina (merah #c41e3a)
✅ **Security** - Login required, staff/admin only

### Color Scheme:
- **Primary:** #c41e3a (Pertamina Red)
- **Secondary:** #003a7a (Pertamina Blue)
- **Success:** #10b981 (Green)
- **Warning:** #f59e0b (Orange)
- **Error:** #ef4444 (Red)

## Customization

### Untuk Menambah Field:
1. Edit model di `models.py`
2. Update view logic di `views.py`
3. Update template untuk menampilkan field baru
4. Run migration: `python manage.py makemigrations` & `python manage.py migrate`

### Untuk Menambah Menu:
1. Edit `apps/dashboard/templates/dashboard/base_admin.html` - tambah link di sidebar
2. Buat view baru di `views.py`
3. Buat template baru di `apps/dashboard/templates/dashboard/`
4. Update `apps/dashboard/urls.py`

## Troubleshooting

### Dashboard tidak bisa diakses:
- Pastikan user adalah staff/admin: `User.objects.filter(username='your_user').update(is_staff=True)`
- Pastikan app dashboard sudah terdaftar di `INSTALLED_APPS` di settings.py
- Run: `python manage.py runserver`

### Data tidak tampil:
- Pastikan models sudah di-import dengan benar
- Cek database apakah ada data
- Check console untuk error messages

## File Structure

```
apps/dashboard/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── tests.py
├── urls.py
├── views.py
├── migrations/
│   └── __init__.py
└── templates/
    └── dashboard/
        ├── base_admin.html       (Base template)
        ├── index.html            (Dashboard home)
        ├── conversations.html    (Conversations list)
        ├── users.html           (Users list)
        ├── documents.html       (Documents list)
        └── analytics.html       (Analytics & reports)
```

## Next Steps

### Fitur yang bisa ditambahkan:
- [ ] Real-time charts dengan Chart.js
- [ ] Export data (CSV, PDF)
- [ ] User activity logs
- [ ] System health monitoring
- [ ] Advanced search/filter
- [ ] Data visualization dashboard
- [ ] Notification system
- [ ] Custom reports builder
- [ ] Admin user roles management
- [ ] API rate limiting dashboard
