import logging
import re
from urllib.parse import urlparse

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


# Free tunnels / scratch hosts → Gmail treats remote images as suspicious.
_UNSAFE_TRACKING_HOST_MARKERS = (
    "trycloudflare.com",
    "ngrok",
    "loca.lt",
    "localtunnel",
    "serveo.net",
    "localhost",
    "127.0.0.1",
)


def _is_unsafe_tracking_host(host: str) -> bool:
    host = (host or "").lower()
    return any(marker in host for marker in _UNSAFE_TRACKING_HOST_MARKERS)


def _same_domain_proxy_is_live(base_url: str) -> bool:
    """True when Namecheap PHP proxy folder is live (not marketing-site Django 404)."""
    import urllib.request

    for probe in (
        f"{base_url.rstrip('/')}/t/ping.txt",
        f"{base_url.rstrip('/')}/t/open.php",
    ):
        try:
            with urllib.request.urlopen(probe, timeout=4) as response:
                body = response.read(120)
                if int(response.status) != 200:
                    continue
                if probe.endswith("ping.txt"):
                    return b"ok" in body.lower()
                content_type = (response.headers.get("Content-Type") or "").lower()
                # Website Django returns HTML 404 for missing /t/ routes.
                if "text/html" in content_type and b"Page not found" in body:
                    continue
                return True
        except Exception:
            continue
    return False


def _origin_backend_reachable(base_url: str) -> bool:
    """True when Cloudflare/Django origin can serve tracking (admin or /t/)."""
    import urllib.error
    import urllib.request

    if not base_url or is_local_tracking_url(base_url):
        return False
    # Prefer paths that prove Django email_platform is up — not a random marketing site.
    for probe in (
        base_url.rstrip("/") + "/admin/",
        base_url.rstrip("/") + "/t/o/healthcheck/",
        base_url.rstrip("/") + "/",
    ):
        try:
            with urllib.request.urlopen(probe, timeout=4) as response:
                if int(response.status) < 500:
                    return True
        except urllib.error.HTTPError as exc:
            # 401/403/404 still mean the host is reachable.
            if int(exc.code) < 500:
                return True
        except Exception:
            continue
    return False


def get_live_origin_backend_url() -> str:
    """Prefer live cloudflared quick-tunnel hostname when available."""
    import json
    import urllib.request

    configured = (getattr(settings, "TRACKING_ORIGIN_BACKEND_URL", "") or "").strip().rstrip("/")
    try:
        with urllib.request.urlopen("http://127.0.0.1:20241/quicktunnel", timeout=1.5) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
            host = (data.get("hostname") or "").strip()
            if host:
                candidate = f"https://{host}"
                if _origin_backend_reachable(candidate):
                    return candidate
    except Exception:
        pass
    if configured and _origin_backend_reachable(configured):
        return configured
    # Never return a dead/stale tunnel URL — callers must fall back cleanly.
    return ""


def can_embed_remote_tracking(
    *,
    campaign_id: str | None = None,
    from_email: str = "",
) -> bool:
    """Embed a pixel whenever we have any public tracking host configured/live."""
    if getattr(settings, "TRACKING_FORCE_REMOTE_PIXEL", False):
        return True
    base = resolve_email_tracking_base_url(
        campaign_id=campaign_id,
        from_email=from_email,
    )
    return bool(base) and not is_local_tracking_url(base)


def resolve_email_tracking_base_url(
    *,
    campaign_id: str | None = None,
    from_email: str = "",
) -> str:
    """
    Prefer same-domain datrixworld.com ONLY when PHP /t/ proxy is live (Gmail-safe).
    Otherwise use live Cloudflare origin so opens still record when images load.
    Never point pixels at the marketing site homepage — /t/ 404s never record opens.
    """
    public = (getattr(settings, "TRACKING_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    origin = get_live_origin_backend_url()
    configured = get_tracking_base_url(campaign_id)
    from_domain = (from_email.split("@")[-1] if "@" in (from_email or "") else "").lower()

    def _matches_from(url: str) -> bool:
        if not from_domain:
            return True
        host = (urlparse(url).hostname or "").lower()
        return host == from_domain or host.endswith("." + from_domain)

    # 1) Same-domain PHP proxy (best for Gmail).
    if public and _matches_from(public) and _same_domain_proxy_is_live(public):
        return public.rstrip("/")

    # 2) Live Cloudflare → Django (works when client loads images).
    if origin and _origin_backend_reachable(origin):
        return origin.rstrip("/")

    if (
        configured
        and not is_local_tracking_url(configured)
        and _same_domain_proxy_is_live(configured)
    ):
        return configured.rstrip("/")

    # Do NOT use public domain when /t/ proxy is missing — that embeds dead pixels.
    return (origin or "").rstrip("/")


def build_open_pixel_url(queue_item_id: str, *, campaign_id: str | None = None) -> str:
    from tracking.pytracking_config import build_pytracking_configuration
    import pytracking

    return pytracking.get_open_tracking_url(
        {"queue_item_id": str(queue_item_id)},
        configuration=build_pytracking_configuration(campaign_id=campaign_id),
    )


def build_view_email_url(queue_item_id: str, *, campaign_id: str | None = None) -> str:
    # Kept for API confirm_url compatibility; opens are tracked by pytracking pixel.
    return build_open_pixel_url(queue_item_id, campaign_id=campaign_id)


def append_text_tracking_link(
    text_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
) -> str:
    # Opens are tracked via HTML pixel when images load; no click required.
    return text_content or ""


def inject_open_tracking_pixel(
    html_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
    from_email: str = "",
) -> str:
    """Inject open pixel + rewrite links via pytracking (D:\\pytracking)."""
    html_content = _prepare_html_document(html_content)
    html_content = _strip_manual_confirm_banner(html_content)

    tracking_base = resolve_email_tracking_base_url(
        campaign_id=campaign_id,
        from_email=from_email,
    )
    if not tracking_base:
        tracking_base = get_live_origin_backend_url()
    if not tracking_base or not can_embed_remote_tracking(
        campaign_id=campaign_id,
        from_email=from_email,
    ):
        logger.info(
            "Skipping remote tracking pixel (no reachable host) base=%s",
            tracking_base,
        )
        return html_content

    if campaign_id:
        from tracking.context import set_campaign_tracking_base_url

        set_campaign_tracking_base_url(str(campaign_id), tracking_base)

    from pytracking.html import adapt_html
    from tracking.pytracking_config import build_pytracking_configuration

    configuration = build_pytracking_configuration(
        campaign_id=campaign_id,
        base_url=tracking_base,
        from_email=from_email,
    )
    logger.info(
        "Embedding tracking pixel base=%s queue_item=%s",
        tracking_base,
        queue_item_id,
    )
    try:
        tracked = adapt_html(
            html_content,
            {"queue_item_id": str(queue_item_id)},
            click_tracking=True,
            open_tracking=True,
            configuration=configuration,
        )
    except Exception:
        logger.exception("pytracking adapt_html failed; falling back to basic pixel")
        tracked = html_content

    # Always append explicit open pixel(s) so Gmail/image proxies still hit us.
    tracked = _append_open_pixel(
        tracked,
        queue_item_id,
        campaign_id=campaign_id,
        base_url=tracking_base,
    )

    # Only dual-embed the public domain when its /t/ proxy is actually live.
    # Embedding a dead datrixworld.com/t/ URL makes opens stay "No" forever.
    public = (getattr(settings, "TRACKING_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if (
        public
        and public.rstrip("/") != tracking_base.rstrip("/")
        and _same_domain_proxy_is_live(public)
    ):
        tracked = _append_open_pixel(
            tracked,
            queue_item_id,
            campaign_id=campaign_id,
            base_url=public,
        )
    return tracked


def _prepare_html_document(html_content: str) -> str:
    """Ensure content is a full HTML document so pytracking can inject into <body>."""
    if not html_content or not html_content.strip():
        return "<html><body></body></html>"
    stripped = html_content.strip()
    if re.search(r"<html[\s>]", stripped, flags=re.IGNORECASE):
        return stripped
    if re.search(r"<body[\s>]", stripped, flags=re.IGNORECASE):
        return f"<html>{stripped}</html>"
    return f"<html><body>{stripped}</body></html>"


def _strip_manual_confirm_banner(html_content: str) -> str:
    """Remove old 'Confirm you received this email' banners from prior versions."""
    html_content = re.sub(
        r'<div[^>]*>\s*<a[^>]*>\s*Confirm you received this email\s*</a>\s*</div>',
        "",
        html_content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html_content = re.sub(
        r'<a[^>]*>\s*Confirm you received this email\s*</a>',
        "",
        html_content,
        flags=re.IGNORECASE,
    )
    html_content = re.sub(
        r'<p[^>]*>\s*<a[^>]*>\s*View this email online\s*</a>\s*</p>',
        "",
        html_content,
        flags=re.IGNORECASE,
    )
    return html_content


def _append_open_pixel(
    html_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
    base_url: str | None = None,
) -> str:
    from tracking.pytracking_config import build_pytracking_configuration
    import pytracking

    pixel_url = pytracking.get_open_tracking_url(
        {"queue_item_id": str(queue_item_id)},
        configuration=build_pytracking_configuration(
            campaign_id=campaign_id,
            base_url=base_url,
        ),
    )
    img = (
        f'<img src="{pixel_url}" width="1" height="1" alt="" border="0" '
        f'style="width:1px;height:1px;border:0;display:block" />'
    )
    if re.search(r"<body[^>]*>", html_content, flags=re.IGNORECASE):
        html_content = re.sub(
            r"(<body[^>]*>)",
            r"\1" + img,
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )
    if re.search(r"</body>", html_content, flags=re.IGNORECASE):
        return re.sub(
            r"</body>",
            img + "</body>",
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )
    return img + html_content + img


def _wrap_links_for_tracking(
    html_content: str,
    queue_item_id: str,
    *,
    campaign_id: str | None = None,
) -> str:
    # Click wrapping is handled by pytracking.adapt_html.
    return html_content


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
            "Opened = Yes when Gmail loads the tracking image after the email is opened. "
            "Resend after tracking fixes — old emails without a pixel cannot update."
            if uses_local_tracking
            else (
                "Opened = Yes when the recipient opens the email and Gmail loads images "
                "(pytracking pixel). Refresh after opening the newest sent email."
            )
        ),
        "tracking_configured": not uses_local_tracking,
    }
