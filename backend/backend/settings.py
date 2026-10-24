from datetime import timedelta
from pathlib import Path
import os
from decouple import config, Csv

# ---------------------------------------------------------------------------
# Base directory
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

# SECRET_KEY must be set explicitly via the environment in production.
# python-decouple raises UndefinedValueError if the key is missing and there
# is no default — this is intentional so a production deployment never
# silently falls back to an insecure key.
# For local development, keep SECRET_KEY= in your backend/.env file.
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# Application-level URLs (used when building absolute media/avatar URLs)
# ---------------------------------------------------------------------------
WEBSITE_URL = config('WEBSITE_URL', default='http://127.0.0.1:8000')

# ---------------------------------------------------------------------------
# External service credentials (Sightengine NSFW moderation)
# ---------------------------------------------------------------------------
SIGHTENGINE_API_USER   = config('SIGHTENGINE_API_USER', default='')
SIGHTENGINE_API_SECRET = config('SIGHTENGINE_API_SECRET', default='')

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
EMAIL_BACKEND  = "django.core.mail.backends.console.EmailBackend"
AUTH_USER_MODEL = 'account.User'

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'account',
    'chat',
    'notification',
    'post',
    'search',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# ---------------------------------------------------------------------------
# ASGI / Django Channels (real-time WebSocket support for chat)
# ---------------------------------------------------------------------------
ASGI_APPLICATION = 'backend.asgi.application'

# InMemoryChannelLayer is correct for a single-process Daphne deployment.
# For multi-process/multi-instance scale, replace with RedisChannelLayer:
#   BACKEND: channels_redis.core.RedisChannelLayer
#   CONFIG:  {'hosts': [('redis', 6379)]}
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# ---------------------------------------------------------------------------
# JWT Authentication
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME' : timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS' : False,
}

# ---------------------------------------------------------------------------
# Refresh-token HttpOnly cookie settings
# These are read in account/api.py when setting/clearing the cookie.
#
# REFRESH_COOKIE_SECURE   — True in production (HTTPS); False for local HTTP
#                           dev.  Defaults to False so the dev server works
#                           without TLS.  In production set to True via .env.
# REFRESH_COOKIE_SAMESITE — 'Lax' is correct for a same-site SPA that sends
#                           credentialed requests from the same origin.
#                           Use 'None' only if the frontend and backend are on
#                           different domains AND you have HTTPS + Secure=True.
# ---------------------------------------------------------------------------
REFRESH_COOKIE_SECURE   = config('REFRESH_COOKIE_SECURE',   default=False, cast=bool)
REFRESH_COOKIE_SAMESITE = config('REFRESH_COOKIE_SAMESITE', default='Lax')

# ---------------------------------------------------------------------------
# WebSocket ticket cache settings
# Short-lived (30 s), single-use UUID tickets for WebSocket authentication.
# Stored in Django's default cache (LocMemCache in a single-process deploy).
# ---------------------------------------------------------------------------
WS_TICKET_TTL = 30  # seconds

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# ---------------------------------------------------------------------------
# CORS / CSRF
# CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS are read from the environment
# so the same settings module works for both local dev and production.
#
# Local dev default:  http://localhost:5173,http://127.0.0.1:5173
# Production example: https://frenzo.example.com
# ---------------------------------------------------------------------------
_cors_default = 'http://localhost:5173,http://127.0.0.1:5173'

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default=_cors_default,
    cast=Csv(),
)

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default=_cors_default,
    cast=Csv(),
)

CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Database — MySQL (primary)
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE'  : config('DB_ENGINE', default='django.db.backends.mysql'),
        'NAME'    : config('DB_NAME',   default='myapp'),
        'USER'    : config('DB_USER',   default='mysqluser'),
        'PASSWORD': config('DB_PASSWORD', default='mysqlpass'),
        'HOST'    : config('DB_HOST',   default='db'),
        'PORT'    : config('DB_PORT',   default='3306'),
        'OPTIONS' : {
            # Keep the connection alive to avoid repeated handshakes.
            # MySQL's default wait_timeout is 8 h; set slightly lower.
            'connect_timeout': 10,
        },
    }
}

# Optional: fall back to SQLite for quick local testing without MySQL.
# Set USE_SQLITE=True in your .env to activate.
if config('USE_SQLITE', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME'  : BASE_DIR / 'db.sqlite3',
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_TZ        = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'   # target of `collectstatic`

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# HTTPS / Security headers
# These are safe to leave enabled even behind a TLS-terminating reverse proxy.
# They are guarded behind DEBUG=False so they do not interfere with local dev.
# ---------------------------------------------------------------------------
if not DEBUG:
    # Tell browsers to use HTTPS for all future requests.
    SECURE_HSTS_SECONDS            = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True

    # Redirect any plain-HTTP request to HTTPS at the Django layer.
    # Disable if your reverse proxy (nginx/Caddy) already handles this.
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)

    # Cookies: mark as Secure and HttpOnly.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE    = True

    # Tell Django it is sitting behind a TLS-terminating proxy.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Prevent MIME-type sniffing.
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Deny embedding in iframes from other origins.
    X_FRAME_OPTIONS = 'DENY'
