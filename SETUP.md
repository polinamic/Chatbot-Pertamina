# Chatbot Pertamina - Setup Guide

AI-powered chatbot untuk otomatisasi IT support dengan RAG (Retrieval-Augmented Generation).

## 📋 Requirements

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- pip dan virtualenv

## 🚀 Installation & Setup

### 1. Clone Repository & Navigate ke Project

```bash
cd Chatbot-Pertamina
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

```bash
# Copy .env.example ke .env
cp .env.example .env

# Edit .env dengan konfigurasi Anda
# - SECRET_KEY: Generate random key
# - DATABASE settings
# - API keys (OpenAI, Pinecone)
```

### 5. Setup Database

```bash
# Create database (jika menggunakan PostgreSQL)
# psql -U postgres
# CREATE DATABASE pertamina_chatbot;

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Create initial data (optional)
python manage.py loaddata fixtures/initial_data.json
```

### 6. Verify Installation

```bash
python manage.py check
```

## 🏃 Running Development Server

```bash
python manage.py runserver
```

Server akan berjalan di `http://localhost:8000`

Admin panel: `http://localhost:8000/admin`

## 📡 API Endpoints

### Authentication
- `POST /api-auth/login/` - Login

### Users
- `POST /api/v1/users/` - Register user
- `GET /api/v1/users/me/` - Get current user
- `PUT /api/v1/users/update_profile/` - Update profile

### Chatbot
- `GET /api/v1/chatbot/conversations/` - List conversations
- `POST /api/v1/chatbot/conversations/` - Create conversation
- `POST /api/v1/chatbot/conversations/{id}/send_message/` - Send message
- `POST /api/v1/chatbot/conversations/{id}/archive/` - Archive conversation

### RAG
- `GET /api/v1/rag/documents/` - List documents
- `POST /api/v1/rag/documents/` - Upload document (admin only)
- `POST /api/v1/rag/documents/{id}/process/` - Process document (admin only)
- `POST /api/v1/rag/documents/search/` - Search documents

## 📁 Project Structure

```
Chatbot-Pertamina/
├── config/                 # Django configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/                   # Django apps
│   ├── chatbot/           # Chatbot functionality
│   ├── rag/               # RAG/Document management
│   ├── users/             # User management
│   └── core/              # Core utilities
├── utils/                 # Helper functions
├── static/                # Static files
├── templates/             # HTML templates
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
└── .env.example          # Environment variables template
```

## 🔧 Best Practices Implemented

✅ **Project Structure**
  - Modular app-based architecture
  - Separation of concerns (models, views, serializers)

✅ **Security**
  - Environment variables for sensitive data
  - CORS protection
  - CSRF middleware
  - SQL injection prevention (ORM)

✅ **Database**
  - Normalized schema
  - Foreign key relationships
  - Proper indexing

✅ **API**
  - RESTful design
  - Pagination
  - Filtering & Search
  - Token authentication

✅ **Configuration**
  - .env file for environment-specific settings
  - Separate settings per environment
  - Logging configuration

✅ **Development**
  - Virtual environment
  - Requirements.txt for dependency management
  - Django management commands

## 📚 Common Commands

```bash
# Run migrations
python manage.py migrate

# Create migrations
python manage.py makemigrations

# Django shell
python manage.py shell

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Flush database
python manage.py flush

# Load data
python manage.py loaddata fixture_name
```

## 🐛 Troubleshooting

**ModuleNotFoundError: No module named 'django'**
```bash
# Ensure virtual environment is activated and dependencies installed
pip install -r requirements.txt
```

**Database connection error**
```bash
# Check PostgreSQL is running and credentials in .env are correct
# psql -U postgres -d pertamina_chatbot
```

**Port 8000 already in use**
```bash
python manage.py runserver 8001
```

## 🚀 Production Deployment

1. Update `.env` dengan production settings
2. Set `DEBUG=False`
3. Collect static files: `python manage.py collectstatic`
4. Use gunicorn: `gunicorn config.wsgi --bind 0.0.0.0:8000`
5. Setup reverse proxy (nginx)
6. Configure SSL/TLS

## 📖 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Langchain Documentation](https://python.langchain.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## 👥 Support

Untuk bantuan atau pertanyaan, silakan buat issue di repository.

---

**Last Updated**: February 2026
