from rest_framework import serializers

from domains.models import SendingDomain
from domains.services import build_dns_records


class DnsRecordSerializer(serializers.Serializer):
    type = serializers.CharField()
    purpose = serializers.CharField()
    host = serializers.CharField()
    host_label = serializers.CharField(required=False)
    value = serializers.CharField()
    verified = serializers.BooleanField()
    required = serializers.BooleanField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class SendingDomainSerializer(serializers.ModelSerializer):
    dns_records = serializers.SerializerMethodField()

    class Meta:
        model = SendingDomain
        fields = (
            "id",
            "domain",
            "is_active",
            "is_default",
            "status",
            "dkim_selector",
            "spf_verified",
            "dkim_verified",
            "dmarc_verified",
            "dns_records",
            "last_verified_at",
            "last_verification_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_dns_records(self, obj):
        records = build_dns_records(obj)
        return DnsRecordSerializer(records, many=True).data


class SendingDomainCreateSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=255)
    is_active = serializers.BooleanField(default=True)
    is_default = serializers.BooleanField(default=False)


class SendingDomainUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_default = serializers.BooleanField(required=False)


class DomainStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    verified = serializers.IntegerField()
    pending = serializers.IntegerField()
    failed = serializers.IntegerField()
    default_configured = serializers.BooleanField()
