from rest_framework import serializers

from email_templates.models import MessagePurpose, MessageVersion


class MessageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageVersion
        fields = (
            "id",
            "version",
            "subject",
            "html_content",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class MessagePurposeSerializer(serializers.ModelSerializer):
    versions = MessageVersionSerializer(many=True, read_only=True)

    class Meta:
        model = MessagePurpose
        fields = ("id", "name", "versions", "created_at", "updated_at")
        read_only_fields = ("id", "versions", "created_at", "updated_at")


class MessagePurposeCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
