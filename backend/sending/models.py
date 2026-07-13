import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class EmailQueueItem(models.Model):
    """Per-recipient outbound email job for a campaign."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SENDING = "sending", _("Sending")
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")
        SKIPPED = "skipped", _("Skipped")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_queue_items",
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="queue_items",
    )
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        on_delete=models.CASCADE,
        related_name="queue_items",
    )
    smtp_server = models.ForeignKey(
        "smtp_servers.SmtpServer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_items",
    )
    to_email = models.EmailField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["campaign", "status"]),
            models.Index(fields=["owner", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "subscriber"],
                name="unique_queue_item_per_campaign_subscriber",
            ),
        ]

    def __str__(self):
        return f"{self.to_email} ({self.status})"
