from django.db.models import Count, Q

from campaigns.models import Campaign
from tracking.models import TrackingEvent


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _event_counts(qs):
    counts = qs.values("event_type").annotate(total=Count("id"))
    result = {item["event_type"]: item["total"] for item in counts}
    return {
        "sent": result.get(TrackingEvent.EventType.SENT, 0),
        "delivered": result.get(TrackingEvent.EventType.DELIVERED, 0),
        "opened": result.get(TrackingEvent.EventType.OPEN, 0),
        "clicked": result.get(TrackingEvent.EventType.CLICK, 0),
        "bounced": result.get(TrackingEvent.EventType.BOUNCE, 0),
        "complaints": result.get(TrackingEvent.EventType.COMPLAINT, 0),
        "unsubscribed": result.get(TrackingEvent.EventType.UNSUBSCRIBE, 0),
    }


def get_overview_stats(user):
    events = TrackingEvent.objects.filter(owner=user)
    counts = _event_counts(events)
    delivered = counts["delivered"] or counts["sent"]
    campaigns_tracked = (
        events.values("campaign_id").distinct().count()
    )

    return {
        **counts,
        "campaigns_tracked": campaigns_tracked,
        "open_rate": _rate(counts["opened"], delivered),
        "click_rate": _rate(counts["clicked"], delivered),
        "bounce_rate": _rate(counts["bounced"], counts["sent"]),
    }


def get_campaign_reports(user, *, search=None, status=None):
    campaigns = Campaign.objects.filter(owner=user)
    if search:
        campaigns = campaigns.filter(
            Q(name__icontains=search) | Q(subject__icontains=search),
        )
    if status:
        campaigns = campaigns.filter(status=status)

    reports = []
    for campaign in campaigns:
        counts = _event_counts(campaign.tracking_events.all())
        sent = counts["sent"]
        delivered = counts["delivered"] or sent
        reports.append({
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "subject": campaign.subject,
            "status": campaign.status,
            "recipient_count": campaign.recipient_count,
            "sent_at": campaign.sent_at,
            **counts,
            "open_rate": _rate(counts["opened"], delivered),
            "click_rate": _rate(counts["clicked"], delivered),
            "bounce_rate": _rate(counts["bounced"], sent),
        })
    return reports
