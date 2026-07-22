import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class InboxMailbox(models.Model):
    """IMAP mailbox added on Unibox — replies sync into the project."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_mailboxes",
    )
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField()
    imap_host = models.CharField(max_length=255)
    imap_port = models.PositiveIntegerField(default=993)
    username = models.CharField(max_length=255)
    password_encrypted = models.TextField()
    verify_ssl = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "email"],
                name="unique_inbox_mailbox_email_per_owner",
            ),
        ]

    def __str__(self):
        return self.name or self.email


class InboxMessage(models.Model):
    """Inbound reply synced via IMAP into the Unibox."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_messages",
    )
    mailbox = models.ForeignKey(
        InboxMailbox,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages",
    )
    smtp_server = models.ForeignKey(
        "smtp_servers.SmtpServer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbox_messages",
    )
    mailbox_email = models.EmailField(blank=True)
    message_id = models.CharField(max_length=512, blank=True, db_index=True)
    imap_uid = models.CharField(max_length=64, blank=True)
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=255, blank=True)
    to_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=998, blank=True)
    snippet = models.CharField(max_length=500, blank=True)
    body_text = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "is_read"]),
            models.Index(fields=["owner", "-received_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "mailbox", "imap_uid"],
                name="unique_inbox_uid_per_unibox_mailbox",
            ),
        ]

    def __str__(self):
        return f"{self.from_email}: {self.subject[:60]}"
