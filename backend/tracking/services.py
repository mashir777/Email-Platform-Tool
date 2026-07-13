import logging
import re
from urllib.parse import quote, urlparse

from django.conf import settings
from django.utils import timezone

from sending.models import EmailQueueItem
from tracking.context import (
    get_campaign_tracking_base_url,
    get_request_tracking_base_url,
)
from tracking.models import TrackingEvent
from tracking.tokens import make_open_token

logger = logging.getLogger(__name__)

# 1x1 transparent GIF
TRANSPARENT_GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00"
    b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def get_tracking_base_url(campaign_id: str | None = None) -> str:
    request_base = get_request_tracking_base_url()
    if request_base:
        return request_base.rstrip("/")
    if campaign_id:
        cached = get_campaign_tracking_base_url(str(campaign_id))
        if cached:
            return cached.rstrip("/")
    return getattr(settings, "TRACKING_PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def is_local_tracking_url(url: str | None = None) -> bool:
    host = urlparse(url or get_tracking_base_url()).hostname or ""
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}


def build_open_pixel_url(queue_item_id: str, *, campaign_id: str | None = None) -> str:
    token = make_open_token(queue_item_id)
    return f"{get_tracking_base_url(campaign_id)}/t/open/{token}.gif"


def build_view_email_url(queue_item_id: str, *, campaign_id: str | None = None) -> str:
    token = make_open_token(queue_item_id)
    return f"{get_tracking_base_url(campaign_id)}/t/view/{token}/"


def append_text_tracking_link(
    text_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
) -> str:
    view_url = build_view_email_url(queue_item_id, campaign_id=campaign_id)
    line = f"\n\nConfirm you received this email: {view_url}\n"
    if text_content:
        return text_content + line
    return line.strip()


def inject_open_tracking_pixel(
    html_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
) -> str:
    if not html_content or not html_content.strip():
        html_content = "<html><body></body></html>"

    pixel_url = build_open_pixel_url(queue_item_id, campaign_id=campaign_id)
    view_url = build_view_email_url(queue_item_id, campaign_id=campaign_id)
    banner = (
        '<div style="margin:0 0 16px;padding:14px;background:#eef2ff;'
        'border:1px solid #c7d2fe;border-radius:8px;text-align:center">'
        f'<a href="{view_url}" style="color:#4338ca;font-weight:600;text-decoration:none">'
        "Confirm you received this email</a></div>"
    )
    img = (
        f'<img src="{pixel_url}" width="1" height="1" alt="" '
        f'style="display:none!important;max-height:0;overflow:hidden" />'
    )
    footer = (
        f'<p style="margin-top:24px;font-size:12px;color:#888;text-align:center">'
        f'<a href="{view_url}" style="color:#888">View this email online</a>'
        f"</p>"
    )
    html_content = _wrap_links_for_tracking(
        html_content,
        queue_item_id,
        campaign_id=campaign_id,
    )
    if re.search(r"<body[^>]*>", html_content, flags=re.IGNORECASE):
        html_content = re.sub(
            r"(<body[^>]*>)",
            r"\1" + banner,
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        html_content = banner + html_content

    if re.search(r"</body>", html_content, flags=re.IGNORECASE):
        html_content = re.sub(
            r"</body>",
            footer + img + "</body>",
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )
        return html_content
    return html_content + footer + img


def _wrap_links_for_tracking(
    html_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
) -> str:
    token = make_open_token(queue_item_id)
    base_url = get_tracking_base_url(campaign_id)

    def replace_href(match):
        quote_char = match.group(1)
        url = match.group(2)
        if not url or url.startswith("#") or url.startswith("mailto:") or "/t/" in url:
            return match.group(0)
        wrapped = f"{base_url}/t/click/{token}/?u={quote(url, safe='')}"
        return f"href={quote_char}{wrapped}{quote_char}"

    return re.sub(r'href=(["\'])(https?://[^"\']+)\1', replace_href, html_content, flags=re.IGNORECASE)


def record_open_event(*, queue_item_id: str, user_agent: str = "", ip_address: str = ""):
    try:
        queue_item = EmailQueueItem.objects.select_related(
            "campaign",
            "subscriber",
        ).get(pk=queue_item_id)
    except EmailQueueItem.DoesNotExist:
        logger.debug("Open tracking: queue item %s not found", queue_item_id)
        return False

    if queue_item.status != EmailQueueItem.Status.SENT:
        return False

    already_opened = TrackingEvent.objects.filter(
        campaign=queue_item.campaign,
        subscriber=queue_item.subscriber,
        event_type=TrackingEvent.EventType.OPEN,
    ).exists()
    if already_opened:
        return True

    TrackingEvent.objects.create(
        owner=queue_item.owner,
        campaign=queue_item.campaign,
        subscriber=queue_item.subscriber,
        event_type=TrackingEvent.EventType.OPEN,
        metadata={
            "queue_item_id": str(queue_item.id),
            "to_email": queue_item.to_email,
            "user_agent": user_agent[:300],
            "ip_address": ip_address[:64],
            "opened_at": timezone.now().isoformat(),
        },
    )
    return True


def _folder_hint(*, queue_status: str, opened: bool) -> tuple[str, str]:
    if queue_status == EmailQueueItem.Status.FAILED:
        return "failed", "Not delivered"
    if queue_status in {EmailQueueItem.Status.PENDING, EmailQueueItem.Status.SENDING}:
        return "pending", "Pending"
    if queue_status == EmailQueueItem.Status.SKIPPED:
        return "skipped", "Skipped"
    if opened:
        return "inbox", "Inbox (opened)"
    return "unknown", "Inbox or Spam — not opened yet"


def get_campaign_delivery_tracking(*, campaign) -> dict:
    open_events = TrackingEvent.objects.filter(
        campaign=campaign,
        event_type=TrackingEvent.EventType.OPEN,
    ).select_related("subscriber")

    opened_subscriber_ids = {event.subscriber_id for event in open_events if event.subscriber_id}
    opened_queue_item_ids = {
        str(event.metadata.get("queue_item_id"))
        for event in open_events
        if event.metadata.get("queue_item_id")
    }
    opened_at_by_subscriber = {
        event.subscriber_id: event.created_at
        for event in open_events
        if event.subscriber_id
    }
    opened_at_by_queue_item = {
        str(event.metadata.get("queue_item_id")): event.created_at
        for event in open_events
        if event.metadata.get("queue_item_id")
    }

    delivered_events = TrackingEvent.objects.filter(
        campaign=campaign,
        event_type=TrackingEvent.EventType.DELIVERED,
    )
    tracking_base_by_queue_item = {
        str(event.metadata.get("queue_item_id")): event.metadata.get("tracking_base_url")
        for event in delivered_events
        if event.metadata.get("queue_item_id")
    }
    campaign_tracking_base = get_campaign_tracking_base_url(str(campaign.id))
    uses_local_tracking = is_local_tracking_url(campaign_tracking_base)

    recipients = []
    opened_count = 0
    delivered_count = 0

    for item in campaign.queue_items.select_related("subscriber").order_by("created_at"):
        opened = (
            item.subscriber_id in opened_subscriber_ids
            or str(item.id) in opened_queue_item_ids
        )
        if item.status == EmailQueueItem.Status.SENT:
            delivered_count += 1
        if opened:
            opened_count += 1

        folder, folder_label = _folder_hint(queue_status=item.status, opened=opened)
        item_tracking_base = (
            tracking_base_by_queue_item.get(str(item.id))
            or campaign_tracking_base
            or get_tracking_base_url(str(campaign.id))
        )
        confirm_url = None
        if item.status == EmailQueueItem.Status.SENT:
            token = make_open_token(str(item.id))
            confirm_url = f"{item_tracking_base.rstrip('/')}/t/view/{token}/"
        recipients.append(
            {
                "email": item.to_email,
                "queue_status": item.status,
                "delivered": item.status == EmailQueueItem.Status.SENT,
                "opened": opened,
                "opened_at": opened_at_by_subscriber.get(item.subscriber_id)
                or opened_at_by_queue_item.get(str(item.id)),
                "folder": folder,
                "folder_label": folder_label,
                "sent_at": item.sent_at,
                "confirm_url": confirm_url,
            },
        )

    total_sent = campaign.queue_items.filter(status=EmailQueueItem.Status.SENT).count()
    return {
        "campaign_id": str(campaign.id),
        "campaign_name": campaign.name,
        "total_recipients": len(recipients),
        "delivered": delivered_count,
        "opened": opened_count,
        "not_opened": max(delivered_count - opened_count, 0),
        "open_rate": round((opened_count / delivered_count) * 100, 1) if delivered_count else 0.0,
        "recipients": recipients,
        "note": (
            "Gmail cannot load tracking images from localhost. Set TRACKING_PUBLIC_BASE_URL "
            "in .env to a public URL (e.g. ngrok) for automatic image opens. Until then, "
            "opens are recorded when the recipient clicks 'Confirm you received this email' "
            "in the message."
            if uses_local_tracking
            else (
                "Gmail does not report Spam vs Inbox. Opened = Yes when the recipient loads "
                "images or clicks a link in the email."
            )
        ),
        "tracking_configured": not uses_local_tracking,
    }
