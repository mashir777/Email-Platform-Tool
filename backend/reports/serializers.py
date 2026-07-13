from rest_framework import serializers


class ReportOverviewSerializer(serializers.Serializer):
    sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    opened = serializers.IntegerField()
    clicked = serializers.IntegerField()
    bounced = serializers.IntegerField()
    complaints = serializers.IntegerField()
    unsubscribed = serializers.IntegerField()
    campaigns_tracked = serializers.IntegerField()
    open_rate = serializers.FloatField()
    click_rate = serializers.FloatField()
    bounce_rate = serializers.FloatField()


class CampaignReportSerializer(serializers.Serializer):
    campaign_id = serializers.UUIDField()
    campaign_name = serializers.CharField()
    subject = serializers.CharField()
    status = serializers.CharField()
    recipient_count = serializers.IntegerField()
    sent_at = serializers.DateTimeField(allow_null=True)
    sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    opened = serializers.IntegerField()
    clicked = serializers.IntegerField()
    bounced = serializers.IntegerField()
    complaints = serializers.IntegerField()
    unsubscribed = serializers.IntegerField()
    open_rate = serializers.FloatField()
    click_rate = serializers.FloatField()
    bounce_rate = serializers.FloatField()
