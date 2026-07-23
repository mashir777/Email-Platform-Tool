from rest_framework import serializers

from inbox.models import InboxMailbox, InboxMessage


class InboxMailboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = InboxMailbox
        fields = (
            "id",
            "name",
            "email",
            "imap_host",
            "imap_port",
            "username",
            "verify_ssl",
            "is_active",
            "last_synced_at",
            "last_sync_message",
            "created_at",
        )
        read_only_fields = fields


class InboxMailboxCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    imap_host = serializers.CharField(max_length=255)
    imap_port = serializers.IntegerField(min_value=1, max_value=65535, default=993)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    password = serializers.CharField(max_length=255)
    verify_ssl = serializers.BooleanField(default=False)


class InboxMessageSerializer(serializers.ModelSerializer):
    mailbox_name = serializers.SerializerMethodField()

    class Meta:
        model = InboxMessage
        fields = (
            "id",
            "mailbox",
            "smtp_server",
            "mailbox_email",
            "mailbox_name",
            "message_id",
            "from_email",
            "from_name",
            "to_email",
            "subject",
            "snippet",
            "body_text",
            "received_at",
            "is_read",
            "created_at",
        )
        read_only_fields = fields

    def get_mailbox_name(self, obj):
        if obj.mailbox_id:
            return obj.mailbox.name or obj.mailbox.email
        if obj.smtp_server_id:
            return obj.smtp_server.name
        return obj.mailbox_email or ""
