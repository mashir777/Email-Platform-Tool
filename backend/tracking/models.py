import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TrackingEvent(models.Model):
    """Email delivery and engagement event."""

    class EventType(models.TextChoices):
        SENT = "sent", _("Sent")
        DELIVERED = "delivered", _("Delivered")
        OPEN = "open", _("Open")
        CLICK = "click", _("Click")
        BOUNCE = "bounce", _("Bounce")
        COMPLAINT = "complaint", _("Complaint")
        UNSUBSCRIBE = "unsubscribe", _("Unsubscribe")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tracking_events",
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="tracking_events",
    )
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    url = models.URLField(max_length=2048, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "event_type"]),
            models.Index(fields=["campaign", "event_type"]),
        ]

    def __str__(self):
        return f"{self.event_type} — {self.campaign_id}"
