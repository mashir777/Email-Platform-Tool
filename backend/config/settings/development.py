from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "*"])

# Local development: SQLite (no MySQL required)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Local development: in-memory cache (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

from urllib.parse import urlparse

_tracking_host = urlparse(
    env("TRACKING_PUBLIC_BASE_URL", default="http://127.0.0.1:8000"),
).hostname
if _tracking_host and _tracking_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, _tracking_host]

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

INTERNAL_IPS = ["127.0.0.1"]

# Local dev: allow domain verify when SPF already exists (user controls DNS via mail host).
DOMAIN_RELAXED_VERIFICATION = env.bool("DOMAIN_RELAXED_VERIFICATION", default=True)

LOGGING["root"]["level"] = env("LOG_LEVEL", default="DEBUG")
LOGGING["loggers"]["django"]["level"] = env("LOG_LEVEL", default="DEBUG")
