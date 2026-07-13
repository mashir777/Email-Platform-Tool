import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SmtpServer(models.Model):
    """SMTP delivery server configuration per user."""

    class Encryption(models.TextChoices):
        NONE = "none", _("None")
        TLS = "tls", _("TLS")
        SSL = "ssl", _("SSL")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="smtp_servers",
    )
    name = models.CharField(max_length=255)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=587)
    username = models.CharField(max_length=255, blank=True)
    password_encrypted = models.TextField(blank=True)
    encryption = models.CharField(
        max_length=10,
        choices=Encryption.choices,
        default=Encryption.TLS,
    )
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    verify_ssl = models.BooleanField(
        default=False,
        help_text=_("Verify the SMTP server SSL certificate. Disable for shared hosting."),
    )
    save_copy_to_sent = models.BooleanField(
        default=True,
        help_text=_(
            "After SMTP send, save a copy to the mailbox Sent folder via IMAP "
            "(shows in Namecheap webmail Sent).",
        ),
    )
    imap_host = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("IMAP host for Sent folder. Leave blank to use the SMTP host."),
    )
    imap_port = models.PositiveIntegerField(default=993)
    hourly_limit = models.PositiveIntegerField(default=100)
    daily_limit = models.PositiveIntegerField(default=1000)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_success = models.BooleanField(null=True, blank=True)
    last_test_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["owner", "is_default"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_smtp_server_name_per_owner",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.host})"
