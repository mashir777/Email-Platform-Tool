import uuid

from django.conf import settings
from django.db import models


class MessagePurpose(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_purposes",
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_message_purpose_per_owner",
            ),
        ]

    def __str__(self):
        return self.name


class MessageVersion(models.Model):
    class Version(models.TextChoices):
        V1 = "v1", "V1"
        V2 = "v2", "V2"
        V3 = "v3", "V3"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.ForeignKey(
        MessagePurpose,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.CharField(max_length=2, choices=Version.choices)
    subject = models.CharField(max_length=255, blank=True)
    html_content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["purpose__name", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["purpose", "version"],
                name="unique_version_per_message_purpose",
            ),
        ]

    def __str__(self):
        return f"{self.purpose.name} — {self.get_version_display()}"

