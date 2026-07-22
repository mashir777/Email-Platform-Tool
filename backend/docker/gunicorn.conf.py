"""Gunicorn config for Docker / EC2."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count())))
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

# Trust nginx / reverse-proxy container IPs for X-Forwarded-* headers
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")
