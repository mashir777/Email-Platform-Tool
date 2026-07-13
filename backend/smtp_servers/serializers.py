from rest_framework import serializers

from smtp_servers.models import SmtpServer


class SmtpServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmtpServer
        fields = (
            "id",
            "name",
            "host",
            "port",
            "username",
            "encryption",
            "from_email",
            "from_name",
            "is_active",
            "is_default",
            "verify_ssl",
            "save_copy_to_sent",
            "imap_host",
            "imap_port",
            "hourly_limit",
            "daily_limit",
            "last_tested_at",
            "last_test_success",
            "last_test_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "last_tested_at",
            "last_test_success",
            "last_test_message",
            "created_at",
            "updated_at",
        )


class SmtpServerCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(min_value=1, max_value=65535, default=587)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    password = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    encryption = serializers.ChoiceField(
        choices=SmtpServer.Encryption.choices,
        default=SmtpServer.Encryption.TLS,
    )
    from_email = serializers.EmailField()
    from_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(default=True)
    is_default = serializers.BooleanField(default=False)
    verify_ssl = serializers.BooleanField(default=False)
    save_copy_to_sent = serializers.BooleanField(default=True)
    imap_host = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    imap_port = serializers.IntegerField(min_value=1, max_value=65535, default=993)
    hourly_limit = serializers.IntegerField(min_value=1, default=100)
    daily_limit = serializers.IntegerField(min_value=1, default=1000)


class SmtpServerUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    host = serializers.CharField(max_length=255, required=False)
    port = serializers.IntegerField(min_value=1, max_value=65535, required=False)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)
    password = serializers.CharField(max_length=255, required=False, allow_blank=True)
    encryption = serializers.ChoiceField(
        choices=SmtpServer.Encryption.choices,
        required=False,
    )
    from_email = serializers.EmailField(required=False)
    from_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_default = serializers.BooleanField(required=False)
    verify_ssl = serializers.BooleanField(required=False)
    save_copy_to_sent = serializers.BooleanField(required=False)
    imap_host = serializers.CharField(max_length=255, required=False, allow_blank=True)
    imap_port = serializers.IntegerField(min_value=1, max_value=65535, required=False)
    hourly_limit = serializers.IntegerField(min_value=1, required=False)
    daily_limit = serializers.IntegerField(min_value=1, required=False)


class SmtpStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    default_configured = serializers.BooleanField()
