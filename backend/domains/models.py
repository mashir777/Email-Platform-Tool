import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SendingDomain(models.Model):
    """Sending domain with DNS verification records."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        VERIFIED = "verified", _("Verified")
        FAILED = "failed", _("Failed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sending_domains",
    )
    domain = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    verification_token = models.CharField(max_length=64)
    dkim_selector = models.CharField(max_length=63, default="epmail")
    dkim_public_key = models.TextField(blank=True)
    dkim_private_key_encrypted = models.TextField(blank=True)
    spf_verified = models.BooleanField(default=False)
    dkim_verified = models.BooleanField(default=False)
    dmarc_verified = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_verification_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "is_default"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "domain"],
                name="unique_sending_domain_per_owner",
            ),
        ]

    def __str__(self):
        return self.domain
