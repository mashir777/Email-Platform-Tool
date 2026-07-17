import os

from django.core.asgi import get_asgi_application

if os.environ.get("VERCEL"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vercel")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()
