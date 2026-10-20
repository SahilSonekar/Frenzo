# 🌟 Frenzo — Social Media Platform

Frenzo is a full-stack social media platform built with **Django REST Framework** and **Vue 3**. It supports user authentication, posts, real-time chat via WebSockets, notifications, search, and automated NSFW image moderation.

---

## 📋 Features

- **JWT Authentication** — secure login, registration, and token refresh
- **User Profiles** — avatars, friend connections, and people-you-may-know suggestions
- **Posts** — create, like, unlike, comment, delete, and report posts; private post support
- **Real-Time Chat** — WebSocket-based messaging between connected users; messages are delivered instantly without polling
- **Notifications** — activity notifications for friend requests, likes, and comments
- **Search** — search for users and posts
- **Media Uploads** — image attachments on posts served through Django's media pipeline
- **NSFW Image Moderation** — uploaded images are screened via the Sightengine API before being published; explicit content is blocked at upload time

---

## 🏗️ Architecture

```
Vue Frontend (Vite · port 5173)
        │
        ├── REST API ──────────────────► Django REST Framework
        │                                        │
        └── WebSocket ─────────────────► Daphne / ASGI
                                                 │
                                          Django Channels
                                                 │
                                          ChatConsumer
                                                 │
                                              MySQL
```

The backend is served by **Daphne** (ASGI), which handles both ordinary HTTP requests and WebSocket connections on port 8000.

---

## 🗂️ Project Structure

```
frenzo/
├── backend/
│   ├── account/            # User model, auth, friend requests
│   ├── chat/
│   │   ├── models.py       # Conversation, ConversationMessage
│   │   ├── api.py          # REST chat endpoints
│   │   ├── consumers.py    # WebSocket ChatConsumer (JWT auth + broadcast)
│   │   ├── routing.py      # WebSocket URL routing
│   │   └── serializers.py
│   ├── notification/       # Notification model and API
│   ├── post/
│   │   ├── models.py       # Post, Comment, Like, Trend, PostAttachment
│   │   ├── api.py
│   │   └── moderation.py   # Sightengine NSFW detection
│   ├── search/             # User and post search
│   ├── scripts/            # Management utility scripts
│   ├── backend/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── asgi.py         # ProtocolTypeRouter (HTTP + WebSocket)
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── views/          # ChatView, FeedView, ProfileView, etc.
│   │   ├── router/
│   │   ├── stores/         # Pinia user store
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── Dockerfile
├── docs/
│   └── uml-diagram.svg
├── docker-compose.yml
└── README.md
```

---

## 🗃️ Database Schema

### UML Class Diagram

![UML Diagram](docs/uml-diagram.svg)

### Core Models

| Model | App | Description |
|---|---|---|
| `User` | `account` | Custom user with email auth, avatar, friend list |
| `FriendshipRequest` | `account` | Friend request with sent/accepted/rejected status |
| `Post` | `post` | User post with body, privacy flag, like/comment counts |
| `PostAttachment` | `post` | Image attachment with NSFW score and flagged status |
| `Comment` | `post` | Comment on a post |
| `Like` | `post` | Like on a post |
| `Trend` | `post` | Tracked hashtag and occurrence count |
| `Conversation` | `chat` | 1-to-1 conversation between two users |
| `ConversationMessage` | `chat` | Individual message in a conversation |
| `Notification` | `notification` | Activity notification for a user |

---

## 💬 Real-Time Chat

Frenzo chat uses two complementary layers:

**REST API** — handles conversation creation, message history retrieval, and sending messages when a WebSocket connection is unavailable.

**WebSocket** — provides instant message delivery to all participants in a conversation without any polling.

### How it works

1. When a user opens a conversation, the frontend opens a WebSocket connection to:
   ```
   ws://localhost:8000/ws/chat/<conversation_id>/?token=<jwt_access_token>
   ```
2. **ChatConsumer** validates the JWT access token from the query string using the same `djangorestframework-simplejwt` library used by the REST APIs. An invalid or missing token closes the connection immediately (code `4001`).
3. **Membership is verified** — a user can only connect to a conversation they belong to. Knowing a conversation UUID is not enough; non-members are rejected (code `4003`).
4. When the user sends a message, the consumer saves it to MySQL using the existing `ConversationMessage` model (identical to the REST endpoint).
5. The saved message is **broadcast** to the channel group for that conversation, so every connected participant receives it in real time.
6. The frontend de-duplicates messages by ID so the sender's own message is not displayed twice.
7. When the user navigates away, the WebSocket closes cleanly and the consumer removes itself from the channel group.

### Channel layer

`InMemoryChannelLayer` is used, which is correct for a single-process Daphne deployment. If the application is scaled across multiple workers or processes, swap in `channels_redis.core.RedisChannelLayer` — no changes to the consumer are required.

### REST fallback

If the WebSocket connection is unavailable or still connecting, the frontend falls back to the existing REST endpoint (`POST /api/chat/<id>/send/`) automatically.

---

## 🔞 NSFW Image Moderation

When a user uploads an image (post attachment), it is checked against the **Sightengine nudity detection API** (`nudity-2.1` model) before being saved.

**How it works:**

1. The uploaded file is sent to the Sightengine API synchronously at upload time.
2. The API returns a nudity analysis. Only the three explicit-content categories are used to calculate the block score: `sexual_activity`, `sexual_display`, and `erotica`. Suggestive or contextual categories (swimwear, cleavage, etc.) are intentionally excluded to avoid false positives.
3. The block score is the maximum of those three values. If it reaches or exceeds **0.5**, the upload is rejected, the file is deleted, and the user receives an error response.
4. If the score is below the threshold, the image is saved and the post proceeds normally. The raw score is stored on `PostAttachment.nsfw_score` for reference.

**Configuration:** Sightengine API credentials are read from environment variables `SIGHTENGINE_API_USER` and `SIGHTENGINE_API_SECRET`.

---

## 🚀 Getting Started with Docker Compose

The recommended way to run Frenzo. Docker Compose starts the Django backend, Vue frontend, and MySQL database together.

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/) and Docker Compose installed

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/SahilSonekar/Frenzo.git
   cd Frenzo
   ```

2. **Create the backend environment file:**
   ```bash
   cp backend/.env.example backend/.env
   ```
   The default values in `.env.example` match the Docker Compose MySQL configuration, so no further changes are needed for a local run. Do **not** commit `.env` — it is listed in `.gitignore`.

3. **Build and start all services:**
   ```bash
   docker compose up --build -d
   ```
   The backend waits for MySQL to pass its health check before starting.

4. **Run database migrations:**
   ```bash
   docker compose exec backend python manage.py migrate
   ```

5. **Create a superuser (optional):**
   ```bash
   docker compose exec backend python manage.py createsuperuser
   ```

6. **Access the application:**
   - Frontend: [http://localhost:5173](http://localhost:5173)
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - Django Admin: [http://localhost:8000/admin](http://localhost:8000/admin)

7. **Stop the services:**
   ```bash
   docker compose down
   ```

> **Note:** The MySQL data volume (`mysql_data`) is preserved when you stop the containers. Use `docker compose down -v` to remove it as well.

---

## 🛠️ Manual Backend Setup

For running the backend directly without Docker.

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure the environment
cp .env.example .env
# Edit .env — set USE_SQLITE=True for local SQLite dev, or configure MySQL credentials

# Apply migrations
python manage.py migrate

# Run the development server (Daphne serves automatically via INSTALLED_APPS)
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000`.

---

## 🌐 Manual Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and connects to the backend at `http://localhost:8000`.

---

## 📦 Backend Dependencies

| Package | Version | Purpose |
|---|---|---|
| `Django` | 4.2 | Web framework |
| `djangorestframework` | 3.14.0 | REST API |
| `djangorestframework-simplejwt` | 5.2.2 | JWT authentication |
| `channels` | 4.0.0 | WebSocket / ASGI layer |
| `daphne` | 4.0.0 | ASGI server |
| `mysqlclient` | 2.2.4 | MySQL database driver |
| `Pillow` | 9.5.0 | Image handling |
| `django-cors-headers` | 3.14.0 | CORS headers |
| `python-decouple` | 3.8 | Environment variable management |
| `requests` | 2.34.2 | Sightengine API calls (NSFW moderation) |

Full list: `backend/requirements.txt`

---

## ⚙️ Tech Stack

### Backend
- Python 3.11
- Django 4.2
- Django REST Framework 3.14
- Django Channels 4.0 + Daphne 4.0 (ASGI / WebSocket)
- SimpleJWT 5.2
- MySQL 8.0 via `mysqlclient`
- Sightengine API (NSFW image moderation)

### Frontend
- Vue 3
- Vite 4
- Pinia (state management)
- Vue Router 4
- Axios
- TailwindCSS 3

### Infrastructure
- Docker Compose
- MySQL 8.0 container with health check
- Persistent `mysql_data` volume

---

## 🔑 API Authentication

All protected endpoints require a JWT access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

| Endpoint | Method | Description |
|---|---|---|
| `/api/signup/` | `POST` | Register a new user |
| `/api/login/` | `POST` | Obtain access and refresh tokens |
| `/api/refresh/` | `POST` | Refresh the access token |
| `/api/me/` | `GET` | Get the authenticated user's profile |

The access token lifetime is 30 days; the refresh token lifetime is 180 days (configurable in `settings.py`).

---

## 🔐 Security Notes

- **`SECRET_KEY`** has an insecure default value in `settings.py`. Set a strong, unique key via the `SECRET_KEY` environment variable in `.env` before deploying.
- **`DEBUG=True`** by default. Set `DEBUG=False` in production.
- **`.env`** is excluded from the repository by `.gitignore`. Never commit it.
- **Sightengine credentials** (`SIGHTENGINE_API_USER`, `SIGHTENGINE_API_SECRET`) must be set in `.env` for NSFW moderation to function.

---

---

## 🚢 Production Deployment Guide

This guide covers deploying Frenzo to a public server. The Docker Compose approach is recommended.

### Required environment variables

#### Backend (`backend/.env`)

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key — long, random, unique | see below |
| `DEBUG` | Must be `False` in production | `False` |
| `ALLOWED_HOSTS` | Comma-separated public hostnames | `api.yoursite.com` |
| `WEBSITE_URL` | Public backend URL (no trailing slash) | `https://api.yoursite.com` |
| `CORS_ALLOWED_ORIGINS` | Trusted frontend origins | `https://yoursite.com` |
| `CSRF_TRUSTED_ORIGINS` | Same as CORS origins (include scheme) | `https://yoursite.com` |
| `DB_ENGINE` | MySQL backend | `django.db.backends.mysql` |
| `DB_NAME` | Database name | `frenzo` |
| `DB_USER` | Database user | `frenzo_user` |
| `DB_PASSWORD` | Database password | _(strong random string)_ |
| `DB_HOST` | MySQL hostname | `db` (Docker) or external host |
| `DB_PORT` | MySQL port | `3306` |
| `SECURE_SSL_REDIRECT` | Redirect HTTP → HTTPS at Django layer | `True` (set `False` if nginx handles it) |
| `SIGHTENGINE_API_USER` | Sightengine moderation API user | _(from sightengine.com)_ |
| `SIGHTENGINE_API_SECRET` | Sightengine moderation API secret | _(from sightengine.com)_ |

Generate a secure `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### Frontend (build-time)

| Variable | Description | Example |
|---|---|---|
| `VITE_API_URL` | Public backend URL | `https://api.yoursite.com` |

`VITE_API_URL` must be set **before** `npm run build` so it is embedded in the JS bundle. The WebSocket URL is derived from it automatically (`https://` → `wss://`).

---

### Docker Compose deployment

```bash
# 1. Prepare environment files
cp backend/.env.example backend/.env      # fill in all production values
cp frontend/.env.example frontend/.env    # set VITE_API_URL

# 2. Build all images (frontend build args must be passed)
VITE_API_URL=https://api.yoursite.com \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. The prod override runs migrate and collectstatic automatically on startup.
#    Verify in logs:
docker compose logs backend
```

The backend starts with Daphne (`daphne -b 0.0.0.0 -p 8000 backend.asgi:application`), which serves both the REST API (HTTP) and real-time chat (WebSocket) on port 8000.

Local development is unchanged:
```bash
docker compose up --build   # still uses runserver via docker-compose.yml
```

---

### Manual / migrations

Apply migrations safely (run before starting the server on a new deployment):
```bash
# Inside Docker
docker compose exec backend python manage.py migrate --noinput

# Without Docker
cd backend
python manage.py migrate --noinput
```

Collect static files:
```bash
python manage.py collectstatic --noinput
```

---

### CORS and ALLOWED_HOSTS

Set these in `backend/.env` to your actual public domains:
```
ALLOWED_HOSTS=api.yoursite.com
CORS_ALLOWED_ORIGINS=https://yoursite.com
CSRF_TRUSTED_ORIGINS=https://yoursite.com
```

---

### WebSocket and HTTPS

WebSocket connections go to the same backend host and port as the REST API:
```
wss://api.yoursite.com/ws/chat/<conversation_id>/?token=<jwt>
```

If a reverse proxy (nginx, Caddy, Traefik) terminates TLS, configure it to:
1. Forward `Upgrade: websocket` and `Connection: upgrade` headers.
2. Set `X-Forwarded-Proto: https` so Django's `SECURE_PROXY_SSL_HEADER` setting works.

Example nginx upstream block:
```nginx
location / {
    proxy_pass         http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header   Upgrade $http_upgrade;
    proxy_set_header   Connection "upgrade";
    proxy_set_header   Host $host;
    proxy_set_header   X-Forwarded-Proto $scheme;
}
```

---

### User-uploaded media (important)

Media files (post images, avatars) are written to `/app/media` inside the backend container. **Container storage is not persistent by default.**

The Docker Compose files already define a named volume `backend_media` mounted at `/app/media`, which survives container restarts. For production deployments across multiple servers or cloud platforms, use an object-storage bucket (AWS S3, Google Cloud Storage, or equivalent) via [django-storages](https://django-storages.readthedocs.io/). The existing upload and NSFW moderation flow does not need to change — only the storage backend.

---

### Post-deployment verification checklist

```
[ ] Backend health:   curl https://api.yoursite.com/api/posts/  → 401 (not 500)
[ ] Login:            POST /api/login/ with test credentials → 200 + tokens
[ ] WebSocket:        ws://api.yoursite.com/ws/chat/<id>/?token=<jwt> → 101
[ ] Static files:     https://yoursite.com/static/... served correctly
[ ] Media files:      Profile avatar URLs resolve correctly
[ ] HTTPS redirect:   http://api.yoursite.com → 301 to https://
[ ] Admin panel:      https://api.yoursite.com/admin/ loads
```

---

## 🗺️ Upcoming Improvements

- Automated test suite
- Redis-backed channel layer for multi-process scaling
- Cloud media storage (AWS S3 / Google Cloud Storage)
- CI/CD pipeline (GitHub Actions)
- API documentation (Swagger / OpenAPI)

---

## 👨‍💻 Author

Made with ❤️ by **Sahil Sonekar**

**GitHub:** [https://github.com/SahilSonekar](https://github.com/SahilSonekar)

**LinkedIn:** [https://www.linkedin.com/in/sahil-sonekar-837a7725b/](https://www.linkedin.com/in/sahil-sonekar-837a7725b/)
