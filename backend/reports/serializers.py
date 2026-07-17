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


class DailyReportDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    sent = serializers.IntegerField()
    opened = serializers.IntegerField()
    waiting = serializers.IntegerField()
    open_rate = serializers.FloatField()


class DailyReportSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    days = DailyReportDaySerializer(many=True)


class DailyReportEmailSerializer(serializers.Serializer):
    queue_item_id = serializers.UUIDField()
    email = serializers.EmailField()
    campaign_id = serializers.UUIDField()
    campaign_name = serializers.CharField()
    sent_at = serializers.DateTimeField()
    opened = serializers.BooleanField()
    status = serializers.CharField()


class DailyReportDetailSerializer(serializers.Serializer):
    date = serializers.DateField()
    sent = serializers.IntegerField()
    opened = serializers.IntegerField()
    waiting = serializers.IntegerField()
    open_rate = serializers.FloatField()
    emails = DailyReportEmailSerializer(many=True)
