from rest_framework import serializers

from subscribers.models import Subscriber, SubscriberList
from subscribers.validators import count_deliverable_subscribers, validate_csv_file


class SubscriberListBriefSerializer(serializers.ModelSerializer):
    """Lightweight list payload nested under emails (no send-stats queries)."""

    class Meta:
        model = SubscriberList
        fields = (
            "id",
            "name",
            "description",
            "source_filename",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SubscriberListSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()
    deliverable_count = serializers.SerializerMethodField()
    total_emails = serializers.SerializerMethodField()
    sent_emails = serializers.SerializerMethodField()
    waiting_emails = serializers.SerializerMethodField()

    class Meta:
        model = SubscriberList
        fields = (
            "id",
            "name",
            "description",
            "source_filename",
            "is_active",
            "is_verified",
            "subscriber_count",
            "deliverable_count",
            "total_emails",
            "sent_emails",
            "waiting_emails",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "source_filename",
            "is_verified",
            "subscriber_count",
            "deliverable_count",
            "total_emails",
            "sent_emails",
            "waiting_emails",
            "created_at",
            "updated_at",
        )

    def get_subscriber_count(self, obj):
        return obj.subscribers.count()

    def get_deliverable_count(self, obj):
        return count_deliverable_subscribers(obj)

    def _send_counts(self, obj):
        cache = getattr(self, "_send_counts_cache", None)
        if cache is None:
            cache = {}
            self._send_counts_cache = cache
        key = str(obj.id)
        if key not in cache:
            from subscribers.services import get_list_send_counts

            owner = obj.owner
            cache[key] = get_list_send_counts(subscriber_list=obj, owner=owner)
        return cache[key]

    def get_total_emails(self, obj):
        return self._send_counts(obj)["total_emails"]

    def get_sent_emails(self, obj):
        return self._send_counts(obj)["sent_emails"]

    def get_waiting_emails(self, obj):
        return self._send_counts(obj)["waiting_emails"]


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
    lists = SubscriberListBriefSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)
    send_status = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "company",
            "industrial_company",
            "phone",
            "status",
            "send_status",
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
            "send_status",
            "subscribed_at",
            "unsubscribed_at",
            "created_at",
            "updated_at",
        )

    def get_send_status(self, obj):
        from subscribers.services import subscriber_was_sent

        owner = self.context.get("owner") or getattr(obj, "owner", None)
        if owner is None:
            return "waiting"
        return "sent" if subscriber_was_sent(
            owner=owner,
            subscriber_id=obj.id,
            subscriber_list=self.context.get("subscriber_list"),
        ) else "waiting"


class SubscriberCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    company = serializers.CharField(required=False, allow_blank=True, max_length=255)
    industrial_company = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
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
    company = serializers.CharField(required=False, allow_blank=True, max_length=255)
    industrial_company = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
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


class SubscriberListVerifySerializer(serializers.Serializer):
    list_id = serializers.UUIDField()


class SubscriberStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    subscribed = serializers.IntegerField()
    unsubscribed = serializers.IntegerField()
    bounced = serializers.IntegerField()
    complained = serializers.IntegerField()
    lists = serializers.IntegerField()
