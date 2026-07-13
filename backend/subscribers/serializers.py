from rest_framework import serializers

from subscribers.models import Subscriber, SubscriberList
from subscribers.validators import count_deliverable_subscribers, validate_csv_file


class SubscriberListSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()
    deliverable_count = serializers.SerializerMethodField()

    class Meta:
        model = SubscriberList
        fields = (
            "id",
            "name",
            "description",
            "is_active",
            "subscriber_count",
            "deliverable_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "subscriber_count",
            "deliverable_count",
            "created_at",
            "updated_at",
        )

    def get_subscriber_count(self, obj):
        return obj.subscribers.count()

    def get_deliverable_count(self, obj):
        return count_deliverable_subscribers(obj)


class SubscriberListCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class SubscriberListUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class SubscriberSerializer(serializers.ModelSerializer):
    list_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    lists = SubscriberListSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Subscriber
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "status",
            "lists",
            "list_ids",
            "subscribed_at",
            "unsubscribed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "lists",
            "full_name",
            "subscribed_at",
            "unsubscribed_at",
            "created_at",
            "updated_at",
        )


class SubscriberCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    status = serializers.ChoiceField(
        choices=Subscriber.Status.choices,
        required=False,
        default=Subscriber.Status.SUBSCRIBED,
    )
    list_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def validate_email(self, value):
        return value.lower().strip()


class SubscriberUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    status = serializers.ChoiceField(choices=Subscriber.Status.choices, required=False)
    list_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate_email(self, value):
        return value.lower().strip()


class SubscriberBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class SubscriberImportSerializer(serializers.Serializer):
    file = serializers.FileField(validators=[validate_csv_file])
    list_id = serializers.UUIDField(required=False, allow_null=True)


class SubscriberStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    subscribed = serializers.IntegerField()
    unsubscribed = serializers.IntegerField()
    bounced = serializers.IntegerField()
    complained = serializers.IntegerField()
    lists = serializers.IntegerField()
