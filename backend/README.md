# 🧠 Frenzo Backend — Powered by Django REST Framework

Welcome to the **backend** of **Frenzo** — a modern social media platform built with **Django 4.2** and **Django REST Framework**.
    
This backend provides RESTful APIs for authentication, user management, posts, comments, likes, chat, notifications, search, media uploads, and automated content moderation. Authentication is handled using **JWT (JSON Web Tokens)**.

---

## 🚀 Key Features

- ✅ JWT Authentication with SimpleJWT
- ✅ Modular Django apps (`account`, `post`, `chat`, `notification`, `search`)
- ✅ RESTful API built with Django REST Framework
- ✅ Media upload support with automated NSFW content moderation
- ✅ CORS configured for frontend integration
- ✅ SQLite for development and PostgreSQL support
- ✅ Docker-ready deployment

---

## 📦 Tech Stack

- **Python 3.10+**
- **Django 4.2**
- **Django REST Framework**
- **SimpleJWT**
- **Pillow**
- **opennsfw2** (NSFW image content moderation)
- **django-cors-headers**
- **SQLite**
- **PostgreSQL (Docker Setup)**

---

## 📁 Project Structure

```text
backend/
├── account/              # Authentication & Custom User Model
├── post/                 # Posts, Likes, Comments & NSFW Moderation
│   └── moderation.py     # NSFW image detection logic
├── chat/                 # Messaging System
├── notification/         # User Notifications
├── search/                # Search Functionality
├── backend/               # Django Project Settings
├── media/                 # Uploaded Media Files
├── manage.py
├── Dockerfile
├── requirements.txt
└── .env
```

---

# ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/SahilSonekar/Frenzo.git
cd Frenzo/backend
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Apply Migrations

```bash
python manage.py migrate
```

---

### 5. Create a Superuser

```bash
python manage.py createsuperuser
```

---

### 6. Start the Development Server

```bash
python manage.py runserver
```

Backend will be available at

```
http://127.0.0.1:8000
```

---

# 🔑 JWT Authentication

Frenzo uses **JWT (JSON Web Tokens)** through **djangorestframework-simplejwt**.

## Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/token/` | POST | Generate Access & Refresh Tokens |
| `/api/token/refresh/` | POST | Refresh Access Token |

### Authorization Header

```
Authorization: Bearer <access_token>
```

---

## JWT Configuration

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=180),
}
```

---

# 🛡️ Content Moderation (NSFW Detection)

Located in `post/moderation.py`, this module screens uploaded post images using **opennsfw2** before they're saved.

**Flow:**
1. An image is uploaded as part of a post.
2. `post/moderation.py` runs the image through the opennsfw2 model, returning an NSFW probability score.
3. If the score exceeds the configured threshold, the upload is rejected and an error is returned to the client instead of the post being created.
4. Images that pass the check continue through the normal post-creation flow.

```python
# post/moderation.py
NSFW_THRESHOLD = 0.8  # Adjust sensitivity as needed
```

> ⚠️ Replace with your actual threshold, and note whether the check runs synchronously during the request or via a background task.

---

# 🌐 CORS Configuration

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
]
```

---

# 🖼 Media Configuration

```python
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
```

Uploaded media files pass through NSFW moderation (`post/moderation.py`) before being served from `/media/` during development.

---

# ⚙️ Django Settings Summary

```python
DEBUG = True
ALLOWED_HOSTS = []
AUTH_USER_MODEL = "account.User"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
TIME_ZONE = "Asia/Kolkata"
```

---

# 📦 Main Dependencies

```text
Django==4.2
djangorestframework==3.14.0
djangorestframework-simplejwt==5.2.2
django-cors-headers==3.14.0
Pillow==9.5.0
PyJWT==2.6.0
asgiref==3.6.0
pytz==2023.3
sqlparse==0.4.3
opennsfw2
```

> ⚠️ Pin the exact `opennsfw2` version (and any dependency it needs, e.g. `onnxruntime` or `tensorflow`) once finalized.

---

# 🔐 Security Notes

- ⚠️ Move `SECRET_KEY` to environment variables in production.
- ⚠️ Set `DEBUG=False` before deployment.
- ✅ No sensitive credentials are committed to the repository.

---

# 📌 Future Improvements

- [ ] Add automated tests
- [ ] Use PostgreSQL as the default database
- [ ] Configure cloud storage (AWS S3 / Google Cloud Storage)
- [ ] Add CI/CD with GitHub Actions
- [ ] Generate API documentation using Swagger/OpenAPI
- [ ] Move NSFW moderation to an async background task for large uploads

---

# 👨‍💻 Author

Made with ❤️ by **Sahil Sonekar**

**GitHub:** [https://github.com/SahilSonekar](https://github.com/SahilSonekar)

**LinkedIn:** [https://www.linkedin.com/in/sahil-sonekar-837a7725b/](https://www.linkedin.com/in/sahil-sonekar-837a7725b/)