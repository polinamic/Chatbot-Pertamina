# SITI - Solusi Interaktif Teknologi Informasi

🤖 **AI-Powered IT Support Chatbot for PT Pertamina**

An intelligent chatbot powered by Retrieval-Augmented Generation (RAG) technology designed to automate IT support for operational staff at PT Pertamina. SITI assists with common issues related to hardware, software, and network problems efficiently.

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Installation Guide](#installation-guide)
- [Database Configuration](#database-configuration)
- [Running the Development Server](#running-the-development-server)
- [API Documentation](#api-documentation)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Project Overview

**SITI** (Solusi Interaktif Teknologi Informasi) is a Django-based conversational AI system designed specifically for PT Pertamina's IT support operations. The system combines:

- **RAG (Retrieval-Augmented Generation)**: Retrieves relevant knowledge from a curated database before generating responses
- **Multi-turn Conversations**: Maintains chat history for contextual understanding
- **Intent Detection**: Identifies user intent and routes to appropriate support channels
- **User Authentication**: Role-based access control (Admin, User, Support Agent, Manager)
- **Activity Logging**: Tracks all user actions for audit purposes

### Key Components

1. **Chatbot Engine** (`apps/chatbot/`): Core RAG pipeline and conversation management
2. **Users Module** (`apps/users/`): Authentication, profiles, and user management
3. **RAG System** (`apps/rag/`): Document ingestion, semantic search, and answer generation
4. **Admin Dashboard** (`apps/dashboard/`): Administrative interface for knowledge base management
5. **Knowledge Base** (`knowledge_base_website_ticket_new.txt`): Curated IT support documentation

---

## ✨ Features

- ✅ **AI Chat Interface**: Intuitive chat UI with markdown rendering
- ✅ **Knowledge Base Management**: Upload and manage IT support documents
- ✅ **Multi-turn Conversations**: Full chat history support with per-conversation storage
- ✅ **User Profiles & Settings**: Customizable user preferences and theme selection
- ✅ **Escalation System**: Automatic escalation to human agents when needed
- ✅ **Role-Based Access Control**: Admin, Support, Manager, and User roles
- ✅ **Activity Logging**: Complete audit trail of user actions
- ✅ **Dark Mode Support**: Light/Dark/Auto theme switching
- ✅ **Responsive Design**: Mobile and desktop optimization

---

## 🛠 Technology Stack

### Backend
- **Framework**: Django 4.2+
- **API**: Django REST Framework
- **Database**: PostgreSQL (Production) / SQLite (Development)
- **Search/Embeddings**: Vector database (Pinecone or local embeddings)
- **LLM**: OpenAI GPT / Local LLM
- **Task Queue**: Celery (optional)
- **Authentication**: JWT + Session-based auth

### Frontend
- **Template Engine**: Django Templates (Jinja2)
- **Styling**: CSS3 with CSS Variables for theming
- **JavaScript**: Vanilla JS + Fetch API
- **Markdown Rendering**: marked.js
- **Icons**: Bootstrap Icons

### DevOps
- **Containerization**: Docker & Docker Compose
- **Version Control**: Git/GitHub
- **Task Automation**: Management commands

---

## 🚀 Installation Guide

### Prerequisites

- Python 3.9+
- PostgreSQL 12+ (or SQLite for development)
- Redis 6+ (optional, for caching)
- Git
- virtualenv or venv

### Step 1: Clone Repository

```bash
git clone https://github.com/polinamic/Chatbot-Pertamina.git
cd Chatbot-Pertamina
```

### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Setup Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=chatbot_pertamina
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Alternatively, for SQLite development:
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3

# LLM Configuration
OPENAI_API_KEY=your-openai-api-key
LLM_MODEL=gpt-3.5-turbo
PINECONE_API_KEY=your-pinecone-key  # If using Pinecone
PINECONE_INDEX_NAME=chatbot-index

# Email Settings (for notifications)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
```

### Step 5: Setup Database

```bash
# Run migrations
python manage.py migrate

# Create superuser for admin
python manage.py createsuperuser

# Optional: Load sample data
python manage.py seed_database
```

### Step 6: Ingest Knowledge Base

```bash
# Ingest the default knowledge base
python ingest_document.py knowledge_base_website_ticket_new.txt
```

---

## 🗄️ Database Configuration

### PostgreSQL Setup (Recommended for Production)

**Windows (using PostgreSQL installer):**
```bash
# Create database
createdb chatbot_pertamina

# Create user
createuser -P chatbot_user
```

**Linux/macOS:**
```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE chatbot_pertamina;
CREATE USER chatbot_user WITH PASSWORD 'your-password';
ALTER ROLE chatbot_user SET client_encoding TO 'utf8';
ALTER ROLE chatbot_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE chatbot_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE chatbot_pertamina TO chatbot_user;
```

### SQLite Setup (Development Only)

For local development, SQLite is already configured:

```python
# .env
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3
```

Then run migrations:
```bash
python manage.py migrate
```

### Database Models

Key models include:

- **User**: Django built-in user model extended with UserProfile
- **UserProfile**: Extended user information (department, role, etc.)
- **UserSettings**: Per-user preferences (theme, notifications, etc.)
- **Document**: Knowledge base documents
- **DocumentChunk**: Semantic chunks of documents with embeddings
- **Conversation**: Chat sessions
- **Message**: Individual messages in conversations
- **ActivityLog**: Audit trail of all user actions
- **EscalationForm**: Tickets for human agent escalation

---

## 🏃 Running the Development Server

### Start Django Development Server

```bash
python manage.py runserver
```

The application will be available at: **http://localhost:8000**

- Chat Interface: `http://localhost:8000/chat/`
- Admin Dashboard: `http://localhost:8000/admin/`
- API Documentation: `http://localhost:8000/api/`

### Default Admin Credentials

After running `createsuperuser`, use those credentials to login at `/admin/`

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_chatbot.py -v

# Run with coverage
pytest --cov=apps
```

---

## 📡 API Documentation

### Authentication Endpoints

```bash
# Signup
POST /api/v1/auth/signup/
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@pertamina.com",
  "password": "SecurePass123"
}

# Login
POST /api/v1/auth/login/
{
  "username": "john_doe",
  "password": "SecurePass123"
}

# Logout
POST /api/v1/auth/logout/
Authorization: Bearer <token>
```

### Chat Endpoints

```bash
# Send message to chatbot
POST /api/v1/rag/chat/
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "Bagaimana cara membuat tiket IT?",
  "session_id": "session_abc123"
}

# Get chat history
GET /api/v1/rag/history/?user_id=1
Authorization: Bearer <token>

# Get conversations
GET /api/v1/conversations/
Authorization: Bearer <token>

# Retrieve specific conversation
GET /api/v1/conversations/{id}/
Authorization: Bearer <token>

# Send message to conversation
POST /api/v1/conversations/{id}/send_message/
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "Message content here"
}

# Delete conversation
DELETE /api/v1/conversations/{id}/
Authorization: Bearer <token>
```

### Admin/Knowledge Base Endpoints

```bash
# Upload document
POST /api/v1/admin/upload/
Authorization: Bearer <admin-token>
Content-Type: multipart/form-data

# Ingest document
POST /api/v1/admin/ingest/
Authorization: Bearer <admin-token>

# Search knowledge base
POST /api/v1/rag/documents/search/
{
  "query": "wifi error"
}
```

---

## 🏗️ Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│        Frontend (HTML/CSS/JavaScript)           │
│  - Chat UI (chat.html)                          │
│  - Profile & Settings (profile.html, settings)  │
│  - Admin Dashboard (dashboard/)                 │
└────────────────┬────────────────────────────────┘
                 │ Fetch API
                 ↓
┌─────────────────────────────────────────────────┐
│         Django Backend (REST API)               │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ Auth System  │  │ Chat Service │             │
│  │ (JWT/Session)│  │ (RAG Engine) │             │
│  └──────────────┘  └──────────────┘             │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ User Profiles│  │ Escalation   │             │
│  │ & Settings   │  │ Management   │             │
│  └──────────────┘  └──────────────┘             │
└────────────────┬────────────────────────────────┘
                 │
         ┌───────┴───────┐
         ↓               ↓
    ┌─────────────┐  ┌──────────────────┐
    │ PostgreSQL  │  │ Vector Database  │
    │ (Main DB)   │  │ (Embeddings)     │
    └─────────────┘  └──────────────────┘
         ↓
    ┌─────────────────────────────────┐
    │ Knowledge Base Files            │
    │ - knowledge_base_*.txt          │
    │ - Document Chunks + Embeddings  │
    └─────────────────────────────────┘
```

### RAG Pipeline Flow

```
User Query
    ↓
Intent Detection (detect_intent_rules)
    ↓
Query Routing (web/escalation/troubleshooting)
    ↓
Document Retrieval (semantic search)
    ↓
Answer Generation (LLM)
    ↓
Response Formatting (markdown + linking)
    ↓
Conversation Storage
    ↓
User Response
```

---

## 🔧 Configuration & Customization

### Modifying LLM Settings

Edit `apps/rag/config.py`:

```python
# Temperature (0-1): Lower = more deterministic, Higher = more creative
LLM_TEMPERATURE = 0.3

# Max tokens in response
LLM_MAX_TOKENS = 500

# Model selection
LLM_MODEL = "gpt-3.5-turbo"
```

### Adding New Escalation Forms

1. Add form definition in `knowledge_base_website_ticket_new.txt`
2. Run: `python ingest_document.py knowledge_base_website_ticket_new.txt`
3. Verify in Admin Dashboard

### Customizing Intent Detection

Edit `apps/rag/services/chat_service.py`, function `detect_intent_rules()` to add new patterns.

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "ModuleNotFoundError: No module named 'apps'"

**Solution**: Ensure you're running from the project root and have installed requirements:
```bash
pip install -r requirements.txt
```

#### 2. Database Connection Error

**Solution**: Check `.env` file database credentials and ensure PostgreSQL is running:
```bash
psql -U postgres -d chatbot_pertamina -c "SELECT 1"
```

#### 3. Chatbot Returns Empty Response

**Solution**: 
- Verify knowledge base is ingested: `python ingest_document.py knowledge_base_website_ticket_new.txt`
- Check Admin Dashboard for documents
- Verify embeddings vector DB is accessible

#### 4. Chat History Not Saving

**Solution**: Ensure `Conversation` and `Message` models are migrated:
```bash
python manage.py migrate
```

#### 5. CORS/Authentication Errors

**Solution**: Verify CSRF token is sent with requests:
```javascript
// In JavaScript
'X-CSRFToken': getCookie('csrftoken')
```

---

## 📚 Additional Resources

### Project Structure

```
Chatbot-Pertamina/
├── apps/
│   ├── chatbot/          # Main chat interface
│   ├── rag/              # RAG engine & semantic search
│   ├── users/            # Authentication & profiles
│   ├── dashboard/        # Admin dashboard
│   ├── core/             # Shared utilities
│   └── ...
├── config/               # Django project settings
├── static/               # CSS, JS, images
├── templates/            # HTML templates
├── knowledge_base_website_ticket_new.txt  # Main KB
├── manage.py             # Django management
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
├── docker-compose.yml    # Docker configuration
└── README.md             # This file
```

### Important Management Commands

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Ingest knowledge base
python ingest_document.py <file.txt>

# Clear cache
python manage.py clear_cache

# Run development server
python manage.py runserver 0.0.0.0:8000
```

### Performance Optimization

- Use `select_related()` and `prefetch_related()` for database queries
- Enable Redis caching for conversation lookups
- Batch document ingestion for large KBs
- Monitor vector DB query times

---

## 📝 Notes for Deployment

### Before Production:

1. ✅ Set `DEBUG=False` in `.env`
2. ✅ Use strong `SECRET_KEY` (generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
3. ✅ Use PostgreSQL instead of SQLite
4. ✅ Enable HTTPS/SSL
5. ✅ Configure allowed hosts
6. ✅ Setup proper logging
7. ✅ Run `python manage.py collectstatic`
8. ✅ Use a production WSGI server (Gunicorn, uWSGI)
9. ✅ Setup automated backups for database
10. ✅ Configure email backend for notifications

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Run migrations in container
docker-compose exec web python manage.py migrate

# Create admin user in container
docker-compose exec web python manage.py createsuperuser
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is proprietary software for PT Pertamina.

---

## 👥 Support

For issues, questions, or support:
- 📧 Email: support@pertamina.local
- 📋 Create an issue on GitHub
- 💬 Contact the development team

---

**Last Updated**: April 2026 | **Version**: 1.0.0
