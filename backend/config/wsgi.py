import os

from django.core.wsgi import get_wsgi_application

if os.environ.get("VERCEL"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vercel")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
