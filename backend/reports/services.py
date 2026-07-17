from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from campaigns.models import Campaign
from sending.models import EmailQueueItem
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


def _parse_report_date(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = timezone.make_aware(datetime.combine(day, time.max))
    return start, end


def _opened_queue_item_ids(user, queue_item_ids: list[str]) -> set[str]:
    """Return queue item ids that have an OPEN event (any time after send)."""
    if not queue_item_ids:
        return set()
    id_set = set(queue_item_ids)
    opened: set[str] = set()
    for metadata in (
        TrackingEvent.objects.filter(
            owner=user,
            event_type=TrackingEvent.EventType.OPEN,
        )
        .values_list("metadata", flat=True)
        .iterator(chunk_size=500)
    ):
        queue_item_id = str((metadata or {}).get("queue_item_id") or "")
        if queue_item_id and queue_item_id in id_set:
            opened.add(queue_item_id)
            if len(opened) >= len(id_set):
                break
    return opened


def get_daily_send_open_report(user, *, date_from=None, date_to=None):
    """
    Per calendar day (by send date): how many emails were sent that day,
    how many of those have been opened since (even if opened weeks later),
    and how many are still waiting (not opened).
    """
    today = timezone.localdate()
    end_day = _parse_report_date(date_to) or today
    start_day = _parse_report_date(date_from) or (end_day - timedelta(days=29))
    if start_day > end_day:
        start_day, end_day = end_day, start_day

    range_start, _ = _day_bounds(start_day)
    _, range_end = _day_bounds(end_day)

    items = list(
        EmailQueueItem.objects.filter(
            owner=user,
            status=EmailQueueItem.Status.SENT,
            sent_at__gte=range_start,
            sent_at__lte=range_end,
        ).values_list("id", "sent_at"),
    )

    sent_by_day: dict = defaultdict(int)
    ids_by_day: dict = defaultdict(list)
    all_ids: list[str] = []
    for item_id, sent_at in items:
        day = timezone.localtime(sent_at).date()
        item_key = str(item_id)
        sent_by_day[day] += 1
        ids_by_day[day].append(item_key)
        all_ids.append(item_key)

    opened_ids = _opened_queue_item_ids(user, all_ids)

    days = []
    cursor = start_day
    while cursor <= end_day:
        sent = sent_by_day.get(cursor, 0)
        if sent > 0:
            day_ids = ids_by_day.get(cursor, [])
            opened = sum(1 for item_id in day_ids if item_id in opened_ids)
            waiting = max(sent - opened, 0)
            days.append(
                {
                    "date": cursor.isoformat(),
                    "sent": sent,
                    "opened": opened,
                    "waiting": waiting,
                    "open_rate": _rate(opened, sent),
                },
            )
        cursor += timedelta(days=1)

    days.reverse()  # newest first
    return {
        "date_from": start_day.isoformat(),
        "date_to": end_day.isoformat(),
        "days": days,
    }


def get_daily_send_open_detail(user, *, day: str):
    """Emails sent on a specific day, with opened / waiting status (opens counted anytime)."""
    report_day = _parse_report_date(day)
    if report_day is None:
        raise ValueError("Invalid date. Use YYYY-MM-DD.")

    start, end = _day_bounds(report_day)
    items = list(
        EmailQueueItem.objects.filter(
            owner=user,
            status=EmailQueueItem.Status.SENT,
            sent_at__gte=start,
            sent_at__lte=end,
        )
        .select_related("campaign")
        .order_by("sent_at")
        .values(
            "id",
            "to_email",
            "sent_at",
            "campaign_id",
            "campaign__name",
        ),
    )

    opened_ids = _opened_queue_item_ids(user, [str(item["id"]) for item in items])
    emails = []
    opened_count = 0
    for item in items:
        item_id = str(item["id"])
        is_opened = item_id in opened_ids
        if is_opened:
            opened_count += 1
        emails.append(
            {
                "queue_item_id": item_id,
                "email": item["to_email"],
                "campaign_id": item["campaign_id"],
                "campaign_name": item["campaign__name"],
                "sent_at": item["sent_at"],
                "opened": is_opened,
                "status": "opened" if is_opened else "waiting",
            },
        )

    sent = len(emails)
    waiting = max(sent - opened_count, 0)
    return {
        "date": report_day.isoformat(),
        "sent": sent,
        "opened": opened_count,
        "waiting": waiting,
        "open_rate": _rate(opened_count, sent),
        "emails": emails,
    }
