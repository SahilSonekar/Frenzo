# Backend Dockerfile
#
# The base image is used for both development and production.
#
# Development (docker-compose.yml):
#   The Compose file overrides CMD with:
#     python manage.py runserver 0.0.0.0:8000
#   This starts Django's dev server which includes hot-reload.
#
# Production (docker-compose.prod.yml):
#   The Compose file overrides CMD with:
#     sh -c "python manage.py collectstatic --noinput && \
#            python manage.py migrate --noinput && \
#            daphne -b 0.0.0.0 -p 8000 backend.asgi:application"
#   This runs collectstatic, applies migrations, then starts Daphne (ASGI)
#   which serves both the REST API and WebSocket connections.

FROM python:3.11-slim

# Prevent .pyc files and enable unbuffered stdout for cleaner Docker logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---------------------------------------------------------------------------
# System dependencies
#   gcc / python3-dev              — required to compile mysqlclient
#   default-libmysqlclient-dev     — MySQL client headers
#   pkg-config                     — used by mysqlclient's build system
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Application source
# ---------------------------------------------------------------------------
COPY . .

# Pre-create directories that are written to at runtime so they exist even
# if no volumes are mounted (avoids permission errors on first run).
RUN mkdir -p /app/media /app/staticfiles

EXPOSE 8000

# Default CMD — used when the Compose file does not override it.
# Daphne is the ASGI server that handles both HTTP and WebSocket connections.
# docker-compose.yml overrides this with `python manage.py runserver` for dev.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]
