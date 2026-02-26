# MSSQL + Django Setup - Panduan Lengkap

## 🗄️ Konfigurasi MSSQL Server

### Status Saat Ini
- ✅ Database `chatbot_pertamina` sudah ada di localhost
- ✅ ODBC Driver 17 for SQL Server sudah terinstall
- ✅ Django settings sudah di-update ke MSSQL

### File Konfigurasi
**`config/settings.py`**
```python
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'chatbot_pertamina',
        'USER': '',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'Trusted_Connection': 'yes',
            'autocommit': True,
        }
    }
}
```

## 🧪 Test Koneksi MSSQL

### Step 1: Test Koneksi Database
```bash
python test_mssql_connection.py
```

**Expected Output:**
```
============================================================
MSSQL Connection & Database Setup Test
============================================================

✅ Koneksi ke MSSQL Server BERHASIL!
   Server: localhost
   Database: chatbot_pertamina
   SQL Server Version: Microsoft SQL Server 2019 (15.0.2000.5) ...

📊 Tabel-tabel yang ada (0):
⚠️  Belum ada tabel di database ini
```

## 📋 Membuat Schema Database

### Option 1: Menggunakan Django Migrations (Recommended)

Django akan otomatis membuat tabel berdasarkan models yang sudah didefinisikan.

```bash
# 1. Create all migrations
python manage.py makemigrations

# 2. Show migration plans
python manage.py sqlmigrate users 0001
python manage.py sqlmigrate users 0002

# 3. Apply migrations ke MSSQL
python manage.py migrate

# 4. Verify tables terbuat
python test_mssql_connection.py
```

**Tabel yang akan di-create:**
```
✅ Django Built-in Tables:
   - auth_user
   - auth_group
   - auth_permission
   - django_content_type
   - django_session
   - django_migrations

✅ Custom Application Tables:
   - users_userprofile
   - chatbot_conversation
   - chatbot_message
   - rag_document
   - rag_documentchunk
   - core_auditrail
   - dashboard_systemconfig
```

### Option 2: Menggunakan Custom SQL Query (Jika Sudah Ada)

Jika Anda sudah membuat query SQL custom, jalankan di SQL Server Management Studio:

```bash
# 1. Buka SSMS
# 2. Connect ke: localhost
# 3. Select database: chatbot_pertamina
# 4. Open New Query
# 5. Paste query Anda
# 6. Execute (F5)
```

Atau jalankan via command line:
```bash
sqlcmd -S localhost -d chatbot_pertamina -i your_script.sql -U sa -P your_password
```

### Option 3: Hybrid Approach

1. **Buat base tables dengan custom SQL** (jika ada foreign keys kompleks)
2. **Jalankan partial migrations** untuk app tertentu:

```bash
python manage.py migrate users
python manage.py migrate chatbot
python manage.py migrate rag
```

## 🔧 Setup Steps

### 1. Test Koneksi MSSQL
```bash
python test_mssql_connection.py
```

### 2. Cek Existing Tables
Jika query SQL sudah dijalankan dan tabel sudah ada:
```bash
python manage.py inspectdb > apps/core/models_auto.py
```

Ini akan auto-generate Django models dari tabel yang ada.

### 3. Create Django Superuser
```bash
python manage.py createsuperuser
# Username: admin
# Email: admin@pertamina.com
# Password: (masukkan password)
```

### 4. Jalankan Development Server
```bash
python manage.py runserver
```

Server akan running di: `http://localhost:8000`

## 🚀 Setup Llama 3.8b + Ollama

### Prerequisites
- Ollama sudah terinstall
- Model llama3:8b sudah terdownload

### Step 1: Jalankan Ollama Service
```bash
# Terminal baru
ollama serve
```

**Expected Output:**
```
starting ollama serve
listening on 127.0.0.1:11434
```

### Step 2: Test Llama Connection
```bash
python test_llama.py
```

**Expected Output:**
```
============================================================
LLAMA 3.8B - Ollama Service Test
============================================================

✅ Ollama Service RUNNING

📦 Available Models:
   - llama3:8b

✅ Llama 3.8b model FOUND

============================================================
Testing Llama 3.8b Generation...
============================================================
```

## 📝 Model Django yang Akan Dibuat

Struktur tabel-tabel untuk signup dan user management:

```sql
-- Users Table (Built-in Django)
CREATE TABLE auth_user (
    id INT PRIMARY KEY IDENTITY(1,1),
    username NVARCHAR(150) UNIQUE NOT NULL,
    first_name NVARCHAR(150),
    last_name NVARCHAR(150),
    email NVARCHAR(254) UNIQUE,
    password NVARCHAR(128) NOT NULL,
    is_staff BIT,
    is_active BIT,
    date_joined DATETIME
);

-- UserProfile Table (Custom)
CREATE TABLE users_userprofile (
    id INT PRIMARY KEY IDENTITY(1,1),
    user_id INT UNIQUE,
    department NVARCHAR(50),
    company NVARCHAR(100),
    phone NVARCHAR(15),
    bio NVARCHAR(MAX),
    is_verified BIT,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);

-- Conversation Table (Chatbot)
CREATE TABLE chatbot_conversation (
    id INT PRIMARY KEY IDENTITY(1,1),
    user_id INT,
    title NVARCHAR(200),
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);

-- Message Table (Chatbot)
CREATE TABLE chatbot_message (
    id INT PRIMARY KEY IDENTITY(1,1),
    conversation_id INT,
    role NVARCHAR(10), -- 'user' or 'assistant'
    content NVARCHAR(MAX),
    created_at DATETIME,
    FOREIGN KEY (conversation_id) REFERENCES chatbot_conversation(id)
);

-- Document Table (RAG)
CREATE TABLE rag_document (
    id INT PRIMARY KEY IDENTITY(1,1),
    title NVARCHAR(255),
    filename NVARCHAR(255),
    content NVARCHAR(MAX),
    created_at DATETIME,
    is_active BIT
);

-- DocumentChunk Table (RAG)
CREATE TABLE rag_documentchunk (
    id INT PRIMARY KEY IDENTITY(1,1),
    document_id INT,
    content NVARCHAR(MAX),
    embedding VARBINARY(MAX),
    chunk_index INT,
    FOREIGN KEY (document_id) REFERENCES rag_document(id)
);
```

## ✅ Verification Checklist

```
□ MSSQL Service Running
  → check di SQL Server Configuration Manager

□ Database chatbot_pertamina Exists
  → python test_mssql_connection.py

□ ODBC Driver 17 Installed
  → Control Panel → Administrative Tools → ODBC Data Sources

□ Django Settings Updated
  → config/settings.py DATABASES = 'mssql'

□ Migrations Applied
  → python manage.py migrate

□ Superuser Created
  → python manage.py createsuperuser

□ Ollama Service Running
  → Terminal: ollama serve

□ Llama 3.8b Model Loaded
  → python test_llama.py

□ Development Server Running
  → python manage.py runserver
```

## 🚨 Troubleshooting

### Error: "Couldn't open library 'ODBC Driver 17 for SQL Server'"
**Solution:**
```bash
# Install ODBC Driver (jika belum ada)
# Windows: Download dari Microsoft official website
# Atau gunakan driver lain yang tersedia:
pip install mssql-django[pyodbc]
```

### Error: "Login failed for user"
```python
# Gunakan Windows Authentication (recommended):
'OPTIONS': {
    'driver': 'ODBC Driver 17 for SQL Server',
    'Trusted_Connection': 'yes',  # ← Key ini penting
}

# Atau gunakan SQL Server Authentication:
'USER': 'sa',
'PASSWORD': 'your_password',
'OPTIONS': {
    'driver': 'ODBC Driver 17 for SQL Server',
}
```

### Error: "Database django_db does not exist"
```bash
# Pastikan database sudah created di MSSQL
# Atau buat via Python:
import pyodbc

conn = pyodbc.connect(
    'Driver={ODBC Driver 17 for SQL Server};'
    'Server=localhost;'
    'Trusted_Connection=yes;'
)
cursor = conn.cursor()
cursor.execute('CREATE DATABASE chatbot_pertamina')
conn.commit()
```

### Ollama Connection Failed
```bash
# Pastikan Ollama service running:
ollama serve

# Atau check port:
netstat -an | find "11434"

# Test dengan curl:
curl http://localhost:11434/api/tags
```

## 📞 Running Everything Together

### Terminal 1 - Ollama Service
```bash
ollama serve
```

### Terminal 2 - Django Development Server
```bash
# Masuk ke project directory
cd c:\AAAAAAAAAAAAAAAAAAA\Semester\ 6\Pertamina\Chatbot-Pertamina

# Activate virtual environment
.venv\Scripts\activate

# Run migrations (first time only)
python manage.py migrate

# Start server
python manage.py runserver
```

### Terminal 3 - Optional: Django Shell untuk Testing
```bash
python manage.py shell

# Test signup
from django.contrib.auth.models import User
from apps.users.models import UserProfile

# Create user
user = User.objects.create_user(
    username='john.doe',
    email='john@pertamina.com',
    password='SecurePass123',
    first_name='John',
    last_name='Doe'
)

# Create profile
profile = UserProfile.objects.create(
    user=user,
    company='Pertamina Regional'
)

print(user)  # User: john.doe
print(profile)  # john.doe - OTHER
```

## 🎉 Selesai!

Database dan LLM sudah siap. Akses:
- **Web App**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Signup**: http://localhost:8000/auth/signup/
- **API**: http://localhost:8000/api/v1/

---
**Last Updated**: February 25, 2026
