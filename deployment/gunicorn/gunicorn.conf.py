"""Gunicorn configuration for email_platform production deployment."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
capture_output = True

proc_name = "email_platform"

wsgi_app = "config.wsgi:application"

raw_env = [
    "DJANGO_SETTINGS_MODULE=config.settings.production",
]

forwarded_allow_ips = "127.0.0.1"
