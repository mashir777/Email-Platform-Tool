import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Campaign(models.Model):
    """Email campaign owned by a platform user."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SCHEDULED = "scheduled", _("Scheduled")
        SENDING = "sending", _("Sending")
        SENT = "sent", _("Sent")
        PAUSED = "paused", _("Paused")
        CANCELLED = "cancelled", _("Cancelled")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaigns",
    )
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    from_name = models.CharField(max_length=255, blank=True)
    from_email = models.EmailField(blank=True)
    # Selected SMTP sender IDs for this campaign (round-robin). Empty = all active.
    smtp_server_ids = models.JSONField(
        default=list,
        blank=True,
        help_text=_("SMTP server UUIDs to send from. Empty uses all active senders."),
    )
    # How many emails one sender sends before rotating. Null = unlimited (first sender only).
    emails_per_sender = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=1,
        help_text=_(
            "Emails per sender before switching to the next. Null = unlimited (first sender only).",
        ),
    )
    html_content = models.TextField(blank=True)
    text_content = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    subscriber_list = models.ForeignKey(
        "subscribers.SubscriberList",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    message_version = models.ForeignKey(
        "email_templates.MessageVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "scheduled_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_campaign_name_per_owner",
            ),
        ]

    def __str__(self):
        return self.name
