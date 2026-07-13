from django.apps import AppConfig


class SmtpServersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smtp_servers"
    verbose_name = "SMTP Servers"
