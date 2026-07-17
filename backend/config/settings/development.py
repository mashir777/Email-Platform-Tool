from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "*"])

# Local development uses MySQL Workbench (Oracle MySQL 8.4 / same DB_* as .env).
# Do not override with SQLite — data must stay consistent across restarts.
# DATABASES inherited from base.py (DB_ENGINE/DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT)

# Avoid "Too many connections": do not keep idle pooled MySQL sockets open.
# (runserver reloads + send timers were leaking CONN_MAX_AGE connections.)
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Local development: in-memory cache (no Redis required)
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
