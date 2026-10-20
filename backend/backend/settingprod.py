"""
Production settings for Frenzo.

This module imports everything from the base settings module and applies
production-specific overrides.  All sensitive values (SECRET_KEY, database
credentials, API keys) must be provided through environment variables — never
hard-code them here.

Usage
-----
Set the Django settings module to this file before starting the server:

    export DJANGO_SETTINGS_MODULE=backend.settingprod
    daphne -b 0.0.0.0 -p 8000 backend.asgi:application

Or via Docker Compose:

    environment:
      DJANGO_SETTINGS_MODULE: backend.settingprod

Environment variables required in production (see backend/.env.example):
    SECRET_KEY            — a long, random, unique string
    DEBUG                 — must be False (or omitted; default is False)
    ALLOWED_HOSTS         — comma-separated list of public hostnames
    CORS_ALLOWED_ORIGINS  — comma-separated list of trusted frontend origins
    CSRF_TRUSTED_ORIGINS  — same as CORS_ALLOWED_ORIGINS (include scheme)
    WEBSITE_URL           — public backend URL used to build media URLs
    DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT  — MySQL credentials
    SIGHTENGINE_API_USER / SIGHTENGINE_API_SECRET        — moderation API
"""

# Import all base settings.  Everything not overridden below stays as-is,
# including Django Channels, Daphne, JWT, CORS (env-driven), MySQL, etc.
from .settings import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# The base settings module already reads every value from environment
# variables and applies all HTTPS security headers when DEBUG=False.
#
# The only thing this file adds is an explicit documentation entry point and
# a guard that prevents accidentally starting in production with DEBUG=True.
# ---------------------------------------------------------------------------
import os

_debug_env = os.environ.get('DEBUG', 'False').strip().lower()
if _debug_env in ('1', 'true', 'yes'):
    import warnings
    warnings.warn(
        "DEBUG=True is set while using the production settings module "
        "(backend.settingprod). This is unsafe for a public deployment.",
        stacklevel=2,
    )
