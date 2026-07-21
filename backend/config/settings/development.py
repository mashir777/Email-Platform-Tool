from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "*"])

# SQLite (db.sqlite3) — inherited from base.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Local development: no API request throttling (campaign polling / page reloads)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/hour",
        "user": "10000/hour",
        "register": "1000/hour",
        "login": "1000/hour",
        "token_refresh": "1000/hour",
        "password_reset": "1000/hour",
        "email_verify": "1000/hour",
    },
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

from urllib.parse import urlparse

# Pixel URLs may use TRACKING_PUBLIC_BASE_URL (domain) or TRACKING_ORIGIN_BACKEND_URL
# (Cloudflare tunnel). Gmail's image proxy hits the Host header of that public URL —
# without it in ALLOWED_HOSTS Django returns DisallowedHost 400 and opens are lost.
for _tracking_url_key in ("TRACKING_PUBLIC_BASE_URL", "TRACKING_ORIGIN_BACKEND_URL"):
    _tracking_host = urlparse(env(_tracking_url_key, default="")).hostname
    if _tracking_host and _tracking_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS = [*ALLOWED_HOSTS, _tracking_host]
# Tunnel hostnames rotate; allow any *.trycloudflare.com subdomain in local / tunnel mode.
if ".trycloudflare.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, ".trycloudflare.com"]

_public_tracking = (env("TRACKING_PUBLIC_BASE_URL", default="http://127.0.0.1:8000") or "").strip()
_origin_tracking = (env("TRACKING_ORIGIN_BACKEND_URL", default="") or "").strip().rstrip("/")
_public_host = (urlparse(_public_tracking).hostname or "").lower()
if _origin_tracking and _public_host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
    # Gmail cannot load 127.0.0.1 pixels — use tunnel / public backend URL from .env.
    TRACKING_PUBLIC_BASE_URL = _origin_tracking

import logging as _logging

try:
    from tracking.services import resolve_send_tracking_base_url as _resolve_send_tracking_base_url

    _tracking_base = _resolve_send_tracking_base_url()
    if _tracking_base:
        if _public_host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
            TRACKING_PUBLIC_BASE_URL = _tracking_base
        _logging.getLogger(__name__).info("Email open tracking URL: %s", _tracking_base)
    else:
        _logging.getLogger(__name__).warning(
            "Email open tracking needs a public URL. Run: cloudflared tunnel --url http://127.0.0.1:8000",
        )
except Exception:
    pass

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

INTERNAL_IPS = ["127.0.0.1"]

# Local dev: allow domain verify when SPF already exists (user controls DNS via mail host).
DOMAIN_RELAXED_VERIFICATION = env.bool("DOMAIN_RELAXED_VERIFICATION", default=True)

LOGGING["root"]["level"] = env("LOG_LEVEL", default="DEBUG")
LOGGING["loggers"]["django"]["level"] = env("LOG_LEVEL", default="DEBUG")

# Windows: RotatingFileHandler rename fails when another process holds the log
# (PermissionError / noisy "Logging error" and flaky 500s under runserver).
LOGGING["handlers"]["file"] = {
    "level": "INFO",
    "class": "logging.FileHandler",
    "filename": str(LOG_DIR / "django.log"),
    "formatter": "verbose",
}
LOGGING["handlers"]["celery_file"] = {
    "level": "INFO",
    "class": "logging.FileHandler",
    "filename": str(LOG_DIR / "celery.log"),
    "formatter": "verbose",
}
