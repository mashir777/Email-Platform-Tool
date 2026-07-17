"""
Vercel serverless settings — signup/login HTTP API only.

No Redis/Celery workers: tasks run eagerly in-process.
Requires DATABASE_URL (Neon / Vercel Postgres).
"""

from __future__ import annotations

import os
from pathlib import Path

from .production import *  # noqa: F401, F403
from .production import LOGGING, env

# In-process Celery (verification emails still send during the request)
CELERY_TASK_ALWAYS_EAGER = True
# Do not turn signup into HTTP 500 if Gmail SMTP fails
CELERY_TASK_EAGER_PROPAGATES = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "email-platform-vercel",
    }
}

# Serverless: do not keep persistent DB connections
if env("DATABASE_URL", default=""):
    DATABASES = {
        "default": env.db("DATABASE_URL"),
    }
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["ATOMIC_REQUESTS"] = True
    # Neon / managed Postgres
    DATABASES["default"].setdefault("OPTIONS", {})
    if "sslmode" not in DATABASES["default"]["OPTIONS"]:
        DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

_hosts = env.list("DJANGO_ALLOWED_HOSTS", default=[])
_extra = [
    ".vercel.app",
    "localhost",
    "127.0.0.1",
]
ALLOWED_HOSTS = list(dict.fromkeys([*_hosts, *_extra]))

vercel_url = os.environ.get("VERCEL_URL", "").strip()
if vercel_url:
    origin = f"https://{vercel_url.removeprefix('https://').removeprefix('http://')}"
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([*CSRF_TRUSTED_ORIGINS, origin]))
    if FRONTEND_URL.startswith(("http://localhost", "http://127.0.0.1")):
        FRONTEND_URL = origin

# Prefer console logs on read-only / ephemeral FS
_log_dir = Path("/tmp/email_platform_logs")
_log_dir.mkdir(parents=True, exist_ok=True)

LOGGING = {
    **LOGGING,
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}

# Avoid redirect loops behind Vercel proxy on edge cases
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# Gmail / SMTP (must be set in Vercel env — empty host means emails never leave)
if not (EMAIL_HOST or "").strip():
    EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
