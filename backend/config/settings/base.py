"""
Django settings for email_platform project.

Split settings: base.py (shared), development.py, production.py.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IS_VERCEL = bool(os.environ.get("VERCEL"))

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    LOG_LEVEL=(str, "INFO"),
)

env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "drf_spectacular",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "campaigns",
    "subscribers",
    "smtp_servers",
    "domains",
    "tracking",
    "analytics",
    "sending",
    "reports",
    "email_templates",
    "settings_app",
    "billing",
    "api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [p for p in [BASE_DIR / "templates"] if p.is_dir()],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "accounts.User"

# Prefer DATABASE_URL (Postgres in Docker/production). Fall back to SQLite for local dev.
_database_url = env("DATABASE_URL", default="")
if _database_url:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", default=str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = env("STATIC_URL", default="/static/")
STATIC_ROOT = BASE_DIR / "staticfiles"
_static_dir = BASE_DIR / "static"
STATICFILES_DIRS = [_static_dir] if _static_dir.is_dir() else []

MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="django-db")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "process-due-scheduled-campaigns": {
        "task": "sending.tasks.process_due_scheduled_campaigns",
        "schedule": 60.0,
    },
    "run-pending-email-queue": {
        "task": "sending.tasks.run_pending_email_queue_task",
        "schedule": 60.0,
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "register": "10/hour",
        "login": "20/hour",
        "token_refresh": "30/hour",
        "password_reset": "5/hour",
        "email_verify": "10/hour",
    },
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173"],
)
# Allow all Vercel app hosts (production + preview): https://*.vercel.app
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w.-]+\.vercel\.app$",
]
_extra_cors_regexes = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
if _extra_cors_regexes:
    CORS_ALLOWED_ORIGIN_REGEXES = [*CORS_ALLOWED_ORIGIN_REGEXES, *_extra_cors_regexes]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")
TRACKING_PUBLIC_BASE_URL = env("TRACKING_PUBLIC_BASE_URL", default="http://127.0.0.1:8000")
# Local Django URL behind tunnel — used by hosted PHP proxy on your domain
TRACKING_ORIGIN_BACKEND_URL = env("TRACKING_ORIGIN_BACKEND_URL", default="")
# Only embed tracking pixels when the public URL matches the From domain
# (e.g. https://datrixworld.com). Free tunnels like trycloudflare/ngrok
# make Gmail hide images and show “This message appears suspicious”.
TRACKING_REQUIRE_SAME_DOMAIN = env.bool("TRACKING_REQUIRE_SAME_DOMAIN", default=True)
TRACKING_FORCE_REMOTE_PIXEL = env.bool("TRACKING_FORCE_REMOTE_PIXEL", default=False)
# Same-domain open-tracking proxy (tunnel-free). When set, email pixels point at
# {TRACKING_PROXY_BASE_URL}/t/open.php and opens are pulled back via events.php.
TRACKING_PROXY_BASE_URL = env("TRACKING_PROXY_BASE_URL", default="")
TRACKING_PROXY_SECRET = env("TRACKING_PROXY_SECRET", default="")

# Reacher (check-if-email-exists) — self-hosted email verification for CSV filtering
REACHER_BACKEND_URL = env("REACHER_BACKEND_URL", default="http://127.0.0.1:8080")
REACHER_API_KEY = env("REACHER_API_KEY", default="")
REACHER_REQUEST_TIMEOUT = env.int("REACHER_REQUEST_TIMEOUT", default=120)
REACHER_BULK_TIMEOUT = env.int("REACHER_BULK_TIMEOUT", default=3600)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@emailplatform.local")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)
EMAIL_VERIFICATION_TOKEN_HOURS = env.int("EMAIL_VERIFICATION_TOKEN_HOURS", default=24)
PASSWORD_RESET_TOKEN_HOURS = env.int("PASSWORD_RESET_TOKEN_HOURS", default=2)

# pytracking library (D:\pytracking) — base URLs are filled at send time from TRACKING_PUBLIC_BASE_URL
PYTRACKING_CONFIGURATION = {
    "append_slash": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Email Platform API",
    "DESCRIPTION": "Production-grade SaaS Email Marketing Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Authentication", "description": "Registration, login, tokens, passwords"},
        {"name": "Profile", "description": "User profile and avatar management"},
        {"name": "Subscribers", "description": "Subscriber lists, contacts, and CSV import"},
        {"name": "Campaigns", "description": "Email campaign builder and scheduling"},
        {"name": "SMTP", "description": "SMTP delivery server configuration and testing"},
        {"name": "Domains", "description": "Sending domain verification and DNS records"},
        {"name": "Reports", "description": "Campaign analytics and performance reporting"},
        {"name": "Sending", "description": "Campaign email queue and delivery"},
    ],
}

LOG_DIR = Path("/tmp/email_platform_logs") if IS_VERCEL else (BASE_DIR / "logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
        "celery_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "celery.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "celery_file"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
