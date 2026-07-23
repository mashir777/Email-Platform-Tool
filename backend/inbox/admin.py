from django.contrib import admin

from inbox.models import InboxMailbox, InboxMessage


@admin.register(InboxMailbox)
class InboxMailboxAdmin(admin.ModelAdmin):
    list_display = ("email", "imap_host", "is_active", "last_synced_at", "owner")
    search_fields = ("email", "name", "imap_host")


@admin.register(InboxMessage)
class InboxMessageAdmin(admin.ModelAdmin):
    list_display = ("from_email", "subject", "mailbox_email", "is_read", "received_at")
    list_filter = ("is_read",)
    search_fields = ("from_email", "subject", "mailbox_email")
    readonly_fields = ("id", "created_at", "updated_at")
