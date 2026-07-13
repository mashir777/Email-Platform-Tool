import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SubscriberList(models.Model):
    """A contact list owned by a platform user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriber_lists",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["owner", "name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_subscriber_list_name_per_owner",
            ),
        ]

    def __str__(self):
        return self.name


class Subscriber(models.Model):
    """An email contact owned by a platform user."""

    class Status(models.TextChoices):
        SUBSCRIBED = "subscribed", _("Subscribed")
        UNSUBSCRIBED = "unsubscribed", _("Unsubscribed")
        BOUNCED = "bounced", _("Bounced")
        COMPLAINED = "complained", _("Complained")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscribers",
    )
    email = models.EmailField()
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBSCRIBED,
        db_index=True,
    )
    lists = models.ManyToManyField(
        SubscriberList,
        through="ListMembership",
        related_name="subscribers",
        blank=True,
    )
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "email"]),
            models.Index(fields=["owner", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "email"],
                name="unique_subscriber_email_per_owner",
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class ListMembership(models.Model):
    """Links subscribers to lists."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    list = models.ForeignKey(
        SubscriberList,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["list", "subscriber"],
                name="unique_list_subscriber_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["list", "added_at"]),
        ]

    def __str__(self):
        return f"{self.subscriber.email} in {self.list.name}"
