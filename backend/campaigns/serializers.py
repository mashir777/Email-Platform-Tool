from rest_framework import serializers

from campaigns.models import Campaign
from email_templates.serializers import MessageVersionSerializer
from subscribers.serializers import SubscriberListSerializer


class CampaignSerializer(serializers.ModelSerializer):
    subscriber_list = SubscriberListSerializer(read_only=True)
    subscriber_list_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    message_version = MessageVersionSerializer(read_only=True)
    message_version_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Campaign
        fields = (
            "id",
            "name",
            "subject",
            "from_name",
            "from_email",
            "smtp_server_ids",
            "emails_per_sender",
            "html_content",
            "text_content",
            "status",
            "subscriber_list",
            "subscriber_list_id",
            "message_version",
            "message_version_id",
            "scheduled_at",
            "sent_at",
            "recipient_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "subscriber_list",
            "message_version",
            "sent_at",
            "recipient_count",
            "created_at",
            "updated_at",
        )


class CampaignCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    subject = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    from_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    from_email = serializers.EmailField(required=False, allow_blank=True, default="")
    html_content = serializers.CharField(required=False, allow_blank=True, default="")
    text_content = serializers.CharField(required=False, allow_blank=True, default="")
    subscriber_list_id = serializers.UUIDField(required=False, allow_null=True)
    message_version_id = serializers.UUIDField(required=False, allow_null=True)
    smtp_server_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    emails_per_sender = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        default=1,
    )


class CampaignUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    subject = serializers.CharField(max_length=255, required=False, allow_blank=True)
    from_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    from_email = serializers.EmailField(required=False, allow_blank=True)
    html_content = serializers.CharField(required=False, allow_blank=True)
    text_content = serializers.CharField(required=False, allow_blank=True)
    subscriber_list_id = serializers.UUIDField(required=False, allow_null=True)
    message_version_id = serializers.UUIDField(required=False, allow_null=True)
    smtp_server_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    emails_per_sender = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )


class CampaignScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()


class CampaignStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    draft = serializers.IntegerField()
    scheduled = serializers.IntegerField()
    sent = serializers.IntegerField()
    cancelled = serializers.IntegerField()


class CampaignTestSendSerializer(serializers.Serializer):
    to_email = serializers.EmailField()
