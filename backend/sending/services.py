import html
import logging
import re
import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from campaigns.models import Campaign
from sending.models import EmailQueueItem
from smtp_servers.connection import connect_smtp_server
from smtp_servers.imap_sent import save_message_to_sent_folder
from smtp_servers.models import SmtpServer
from subscribers.models import ListMembership, Subscriber
from subscribers.validators import is_undeliverable_email
from tracking.models import TrackingEvent
from tracking.services import append_text_tracking_link, get_tracking_base_url, inject_open_tracking_pixel

logger = logging.getLogger(__name__)

MIN_SEND_INTERVAL_SECONDS = 1


def _list_membership_added_at_by_subscriber(*, subscriber_list) -> dict:
    return {
        row["subscriber_id"]: row["added_at"]
        for row in ListMembership.objects.filter(list=subscriber_list).values(
            "subscriber_id",
            "added_at",
        )
    }


def _subscribers_sent_since_list_import(
    *,
    owner,
    subscriber_list,
    subscriber_ids,
    membership_added_at: dict | None = None,
) -> set:
    """Subscriber IDs already mailed after they were last imported into this list."""
    if membership_added_at is None:
        membership_added_at = _list_membership_added_at_by_subscriber(
            subscriber_list=subscriber_list,
        )

    blocked = set()
    if not subscriber_ids:
        return blocked

    for row in EmailQueueItem.objects.filter(
        owner=owner,
        status=EmailQueueItem.Status.SENT,
        subscriber_id__in=subscriber_ids,
        sent_at__isnull=False,
    ).values("subscriber_id", "sent_at"):
        sub_id = row["subscriber_id"]
        added_at = membership_added_at.get(sub_id)
        if added_at is None or row["sent_at"] >= added_at:
            blocked.add(sub_id)
    return blocked


def _should_requeue_after_csv_reimport(*, queue_item, membership_added_at: dict) -> bool:
    added_at = membership_added_at.get(queue_item.subscriber_id)
    if not added_at:
        return False
    if queue_item.status == EmailQueueItem.Status.SENT:
        return not queue_item.sent_at or queue_item.sent_at < added_at
    if queue_item.status == EmailQueueItem.Status.SKIPPED:
        return "Already sent previously" in (queue_item.last_error or "")
    return False


def _requeue_item_for_resend(*, queue_item, assigned_server) -> None:
    queue_item.status = EmailQueueItem.Status.PENDING
    queue_item.last_error = ""
    queue_item.sent_at = None
    queue_item.smtp_server = assigned_server
    queue_item.save(
        update_fields=["status", "last_error", "sent_at", "smtp_server", "updated_at"],
    )


def get_effective_daily_limit(smtp_server: SmtpServer) -> int:
    """Daily send cap — respects simple warmup ramp when enabled."""
    configured = max(int(smtp_server.daily_limit or 1), 1)
    if not getattr(smtp_server, "warmup_enabled", False):
        return configured
    current = int(smtp_server.warmup_current_daily or 0)
    if current <= 0:
        current = max(int(smtp_server.warmup_start_daily or 1), 1)
    target = max(int(smtp_server.warmup_target_daily or current), current)
    return max(1, min(configured, current, target))


def compute_send_interval_seconds(smtp_server: SmtpServer) -> int:
    """Seconds between consecutive sends based on hourly limit (customizable, min 1s)."""
    hourly = max(int(smtp_server.hourly_limit or 1), 1)
    return max(MIN_SEND_INTERVAL_SECONDS, 3600 // hourly)


def get_next_send_in_seconds(*, smtp_server: SmtpServer | None) -> int:
    """Seconds until the next email can leave this SMTP mailbox (0 = now)."""
    if not smtp_server:
        return 0
    interval = compute_send_interval_seconds(smtp_server)
    last_item = (
        EmailQueueItem.objects.filter(
            smtp_server_id=smtp_server.id,
            status=EmailQueueItem.Status.SENT,
            sent_at__isnull=False,
        )
        .order_by("-sent_at")
        .first()
    )
    if not last_item or not last_item.sent_at:
        return 0
    elapsed = (timezone.now() - last_item.sent_at).total_seconds()
    return max(0, int(interval - elapsed))


def _count_sent_since(*, smtp_server_id, since):
    return EmailQueueItem.objects.filter(
        smtp_server_id=smtp_server_id,
        status=EmailQueueItem.Status.SENT,
        sent_at__gte=since,
    ).count()


def can_send_email(*, smtp_server: SmtpServer) -> bool:
    now = timezone.now()
    if (
        _count_sent_since(smtp_server_id=smtp_server.id, since=now - timedelta(hours=1))
        >= smtp_server.hourly_limit
    ):
        return False
    daily_cap = get_effective_daily_limit(smtp_server)
    if (
        _count_sent_since(smtp_server_id=smtp_server.id, since=now - timedelta(days=1))
        >= daily_cap
    ):
        return False

    last_item = (
        EmailQueueItem.objects.filter(
            smtp_server_id=smtp_server.id,
            status=EmailQueueItem.Status.SENT,
            sent_at__isnull=False,
        )
        .order_by("-sent_at")
        .first()
    )
    if last_item and last_item.sent_at:
        interval = compute_send_interval_seconds(smtp_server)
        if now < last_item.sent_at + timedelta(seconds=interval):
            return False
    return True


def get_next_pending_queue_item(*, smtp_server_id=None):
    """Next pending item in queue order (oldest first = list order when queued)."""
    qs = EmailQueueItem.objects.filter(
        status=EmailQueueItem.Status.PENDING,
        campaign__status=Campaign.Status.SENDING,
    ).select_related("campaign", "subscriber", "smtp_server", "smtp_server__owner")
    if smtp_server_id:
        qs = qs.filter(smtp_server_id=smtp_server_id)
    return qs.order_by("created_at", "id").first()


def has_pending_queue_items() -> bool:
    return EmailQueueItem.objects.filter(
        status=EmailQueueItem.Status.PENDING,
        campaign__status=Campaign.Status.SENDING,
    ).exists()


def run_pending_email_queue() -> dict:
    """
    Send one pending email at a time in queue/list order.

    Do not send in parallel across SMTP servers — that breaks
    "first sender N, then next sender" sequencing.
    """
    item = get_next_pending_queue_item()
    if not item:
        return {"processed": 0}

    smtp_server = item.smtp_server or get_default_smtp_server(item.campaign.owner)
    if not smtp_server:
        return {"processed": 0}
    if not can_send_email(smtp_server=smtp_server):
        return {"processed": 0}

    if not item.smtp_server_id:
        item.smtp_server = smtp_server
        item.save(update_fields=["smtp_server", "updated_at"])

    process_queue_item(queue_item=item)
    finalize_campaign_if_complete(campaign=item.campaign)
    return {"processed": 1}


def get_default_smtp_server(owner):
    server = (
        SmtpServer.objects.filter(owner=owner, is_active=True, is_default=True)
        .order_by("-updated_at")
        .first()
    )
    if server:
        return server
    return (
        SmtpServer.objects.filter(owner=owner, is_active=True)
        .order_by("-updated_at")
        .first()
    )


def get_active_smtp_servers(owner):
    return list(
        SmtpServer.objects.filter(owner=owner, is_active=True).order_by("created_at"),
    )


def resolve_campaign_smtp_servers(campaign: Campaign) -> list[SmtpServer]:
    """Active SMTP senders for this campaign (selected IDs in saved order, or all active)."""
    active = get_active_smtp_servers(campaign.owner)
    active_by_id = {str(server.id): server for server in active}
    raw_ids = getattr(campaign, "smtp_server_ids", None) or []
    if not raw_ids:
        return active
    selected: list[SmtpServer] = []
    for value in raw_ids:
        server = active_by_id.get(str(value))
        if server is not None and server not in selected:
            selected.append(server)
    if not selected:
        raise ValidationError(
            {
                "smtp_server_ids": [
                    "Select at least one active sender (SMTP mailbox) for this campaign.",
                ],
            },
        )
    return selected


def _subscribed_recipients_in_list_order(subscriber_list) -> list[Subscriber]:
    """List emails in upload/membership order (first uploaded = index 0)."""
    ordered_ids = list(
        ListMembership.objects.filter(list=subscriber_list)
        .order_by("added_at", "id")
        .values_list("subscriber_id", flat=True),
    )
    if not ordered_ids:
        return []
    by_id = {
        subscriber.id: subscriber
        for subscriber in Subscriber.objects.filter(
            id__in=ordered_ids,
            status=Subscriber.Status.SUBSCRIBED,
        )
    }
    return [by_id[subscriber_id] for subscriber_id in ordered_ids if subscriber_id in by_id]


def _pick_smtp_server(
    servers: list[SmtpServer],
    index: int,
    emails_per_sender: int | None = None,
) -> SmtpServer | None:
    """
    Top sender first: each selected sender sends N from the list (next rows only),
    then stop. No wrap back. N defaults to 1 when unset.
    """
    batch = emails_per_sender if emails_per_sender and emails_per_sender > 0 else 1
    sender_index = index // batch
    if sender_index >= len(servers):
        return None
    return servers[sender_index]


def _campaign_batch_cap(campaign: Campaign, servers: list[SmtpServer]) -> int:
    """Exact send count for one pass: emails_per_sender × selected senders."""
    per_sender = getattr(campaign, "emails_per_sender", None) or 1
    return max(1, int(per_sender)) * len(servers)


def _demote_excess_pending(
    *,
    campaign: Campaign,
    allowed_subscriber_ids: set,
    smtp_server: SmtpServer,
) -> None:
    """Any PENDING beyond this pass's cap must not send (strict limit)."""
    extras = campaign.queue_items.filter(
        status__in=[
            EmailQueueItem.Status.PENDING,
            EmailQueueItem.Status.SENDING,
            EmailQueueItem.Status.FAILED,
        ],
    ).exclude(subscriber_id__in=allowed_subscriber_ids).select_related("subscriber")
    for item in extras:
        _skip_over_send_limit(
            campaign=campaign,
            subscriber=item.subscriber,
            smtp_server=smtp_server,
            existing=item,
        )


def _skip_over_send_limit(
    *,
    campaign: Campaign,
    subscriber: Subscriber,
    smtp_server: SmtpServer,
    existing: EmailQueueItem | None = None,
) -> None:
    """Skip remaining list rows after each sender has used its limit once."""
    message = (
        "Sending limit reached — each selected sender sent its set limit; campaign stopped."
    )
    if existing is None:
        EmailQueueItem.objects.create(
            owner=campaign.owner,
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=smtp_server,
            to_email=subscriber.email,
            status=EmailQueueItem.Status.SKIPPED,
            last_error=message,
        )
        return
    if existing.status == EmailQueueItem.Status.SENT:
        return
    existing.smtp_server = smtp_server
    existing.status = EmailQueueItem.Status.SKIPPED
    existing.last_error = message
    existing.save(
        update_fields=["smtp_server", "status", "last_error", "updated_at"],
    )


def _rewrite_signature_sender_name(content: str, sender_display: str) -> str:
    """
    Put the active Sender-page From name on the signature line after Best,/Regards,.
    Works even when the template still has a hardcoded name like \"David Wilson\".
    """
    sender_display = (sender_display or "").strip()
    if not content or not sender_display:
        return content

    # Best, / Best regards, / Regards, / Thanks, then line break(s), then the name line.
    pattern = re.compile(
        r"(?P<prefix>"
        r"(?:Best(?:\s+regards)?|Regards|Thanks|Thank you)\s*,?\s*"
        r"(?:<br\s*/?>\s*|\r?\n\s*)+)"
        r"(?P<name>[^\r\n<]{1,80}?)"
        r"(?P<suffix>\s*(?:<br\s*/?>|\r?\n|$))",
        re.IGNORECASE,
    )

    def _is_company_line(name: str) -> bool:
        lowered = name.strip().lower()
        if not lowered:
            return True
        if "datrix" in lowered or "http" in lowered or "www." in lowered:
            return True
        if "|" in name or "@" in name:
            return True
        return False

    def repl(match: re.Match) -> str:
        name = match.group("name").strip()
        if _is_company_line(name):
            return match.group(0)
        if name.lower() == sender_display.lower():
            return match.group(0)
        return f"{match.group('prefix')}{sender_display}{match.group('suffix')}"

    return pattern.sub(repl, content, count=1)


def _personalize(
    content: str,
    subscriber: Subscriber | None,
    *,
    sender_name: str = "",
    sender_email: str = "",
    sender_names_to_swap: list[str] | None = None,
) -> str:
    if not content:
        return ""

    def normalize_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    fields: dict[str, str] = {}
    if subscriber is not None:
        display_name = subscriber.full_name or subscriber.first_name or ""
        company = getattr(subscriber, "company", "") or ""
        industrial_company = getattr(subscriber, "industrial_company", "") or ""

        for key, value in (subscriber.custom_fields or {}).items():
            text = str(value or "")
            raw = str(key or "").strip()
            if not raw:
                continue
            fields[raw] = text
            fields[raw.lower()] = text
            norm = normalize_key(raw)
            if norm:
                fields[norm] = text

        # Canonical subscriber fields win over CSV aliases when both exist.
        fields["email"] = subscriber.email
        canonical_fields = {
            "name": display_name,
            "first_name": subscriber.first_name or display_name,
            "firstname": subscriber.first_name or display_name,
            "last_name": subscriber.last_name or "",
            "lastname": subscriber.last_name or "",
            "full_name": display_name,
            "fullname": display_name,
            "company": company,
            "company_name": company,
            "industrial_company": industrial_company,
            "industrialcompany": industrial_company,
            "industry": industrial_company,
            "phone": subscriber.phone or "",
        }
        for key, value in canonical_fields.items():
            fields[key] = value
            fields[normalize_key(key)] = value

    # SMTP sender display name (signature) — from Sender page "From name".
    sender_display = (sender_name or "").strip()
    sender_mail = (sender_email or "").strip()
    sender_fields = {
        "sender_name": sender_display,
        "sender": sender_display,
        "from_name": sender_display,
        "Sender Name": sender_display,
        "Sender": sender_display,
        "sender_email": sender_mail,
        "from_email": sender_mail,
    }
    for key, value in sender_fields.items():
        fields[key] = value
        fields[key.lower()] = value
        fields[normalize_key(key)] = value
        fields[key.replace("_", " ")] = value

    placeholder_pattern = re.compile(
        r"\{\{\s*([^{}]+?)\s*\}\}|\[([^\[\]]+?)\]",
    )

    def replace_placeholder(match):
        raw_key = (match.group(1) or match.group(2) or "").strip()
        if not raw_key:
            return match.group(0)
        if raw_key in fields:
            return fields[raw_key]
        lowered = raw_key.lower()
        if lowered in fields:
            return fields[lowered]
        normalized = normalize_key(raw_key)
        if normalized in fields:
            return fields[normalized]
        return match.group(0)

    result = placeholder_pattern.sub(replace_placeholder, content)

    # Hardcoded other-sender names → current SMTP From name.
    if sender_display:
        for other in sender_names_to_swap or []:
            other = (other or "").strip()
            if not other or other.lower() == sender_display.lower():
                continue
            if other in result:
                result = result.replace(other, sender_display)

        # Always rewrite the signature name line after Best,/Regards, from Sender From name.
        result = _rewrite_signature_sender_name(result, sender_display)

    return result


def _format_html_message(content: str) -> str:
    """Render textarea/plain-text messages as readable, email-safe HTML."""
    content = (content or "").strip()
    if not content:
        return ""
    if re.search(r"<(?:html|body)\b", content, flags=re.IGNORECASE):
        return content

    has_html_tags = bool(
        re.search(r"</?[a-z][^>]*>", content, flags=re.IGNORECASE),
    )
    body = content if has_html_tags else html.escape(content)
    if not has_html_tags:
        body = body.replace("\r\n", "\n").replace("\r", "\n")
        body = body.replace("\n", "<br>\n")

    return (
        '<div data-email-body="true" '
        'style="font-family:Arial,Helvetica,sans-serif;font-size:15px;'
        'line-height:1.6;color:#1f2937;max-width:640px;">'
        f"{body}</div>"
    )


def _resolve_reply_to_email(*, smtp_server: SmtpServer, sender_email: str) -> str:
    """
    Reply must go to BOTH:
    1) the address the mail was sent from
    2) Reply-To (SMTP reply_to_email or account default_reply_to), when set
    """
    send_from = (sender_email or "").strip() or (getattr(smtp_server, "from_email", "") or "").strip()

    per_server = (getattr(smtp_server, "reply_to_email", "") or "").strip()
    owner = getattr(smtp_server, "owner", None)
    if owner is None and getattr(smtp_server, "owner_id", None):
        owner = smtp_server.owner
    owner_default = (getattr(owner, "default_reply_to", "") or "").strip() if owner else ""
    shared = per_server or owner_default

    # No shared Reply-To → leave empty so clients reply to From only.
    if not shared:
        return ""
    # Shared same as From → one address is enough.
    if send_from and shared.lower() == send_from.lower():
        return ""
    # Both required: From (sender) + Reply-To inbox.
    if send_from:
        return f"{send_from}, {shared}"
    return shared


def send_message_via_smtp(
    *,
    smtp_server: SmtpServer,
    to_email: str,
    subject: str,
    html_content: str = "",
    text_content: str = "",
    from_email: str = "",
    from_name: str = "",
    save_to_sent: bool = True,
):
    sender_email = (from_email or smtp_server.from_email or "").strip()
    sender_name = from_name or smtp_server.from_name
    from_header = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_header
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender_email.split("@")[-1] if "@" in sender_email else None)
    reply_to = _resolve_reply_to_email(
        smtp_server=smtp_server,
        sender_email=sender_email,
    )
    if reply_to:
        if "Reply-To" in message:
            del message["Reply-To"]
        # Explicit mailbox-list so clients put both addresses on Reply.
        message["Reply-To"] = reply_to
    # MIMEMultipart already sets MIME-Version; setting it again makes a duplicate
    # header that AWS SES rejects with 554 "Duplicate header 'MIME-Version'".

    body_text = text_content or "This email requires an HTML-capable client."
    message.attach(MIMEText(body_text, "plain", "utf-8"))
    if html_content:
        message.attach(MIMEText(html_content, "html", "utf-8"))

    with connect_smtp_server(smtp_server=smtp_server) as server:
        envelope_from = sender_email or (smtp_server.from_email or "").strip()
        raw = message.as_string()
        # Ensure Reply-To survives serialization (some policies collapse address lists).
        if reply_to and "Reply-To:" not in raw and "reply-to:" not in raw.lower():
            raw = f"Reply-To: {reply_to}\r\n" + raw
        server.sendmail(envelope_from, [to_email], raw)

    if save_to_sent:
        save_message_to_sent_folder(smtp_server=smtp_server, message=message)


def send_message_via_django(
    *,
    to_email: str,
    subject: str,
    html_content: str = "",
    text_content: str = "",
    from_email: str = "",
    from_name: str = "",
):
    sender_email = from_email or settings.DEFAULT_FROM_EMAIL
    sender_name = from_name
    from_header = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    body_text = text_content or "This email requires an HTML-capable client."
    email = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_header,
        to=[to_email],
    )
    if html_content:
        email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def _validate_campaign_for_send(campaign: Campaign, *, allow_sending: bool = False):
    allowed = {
        Campaign.Status.DRAFT,
        Campaign.Status.SCHEDULED,
        Campaign.Status.PAUSED,
    }
    if allow_sending:
        allowed.add(Campaign.Status.SENDING)

    if campaign.status not in allowed:
        raise ValidationError(
            {"status": ["Only draft, scheduled, paused, or in-progress campaigns can be sent."]},
        )
    if not campaign.subscriber_list_id:
        raise ValidationError({"subscriber_list_id": ["A subscriber list is required."]})
    if not campaign.subject:
        raise ValidationError({"subject": ["Subject is required to send."]})
    if not campaign.html_content and not campaign.text_content:
        raise ValidationError(
            {"html_content": ["Email content is required to send."]},
        )

    from subscribers.validators import count_deliverable_subscribers

    if count_deliverable_subscribers(campaign.subscriber_list) == 0:
        raise ValidationError(
            {
                "subscriber_list_id": [
                    "This list has no real email addresses. "
                    "Remove @example.com test data and add Gmail or work emails.",
                ],
            },
        )


def _validate_smtp_configured(owner):
    servers = get_active_smtp_servers(owner)
    if not servers:
        raise ValidationError(
            {
                "smtp": [
                    "No active SMTP server configured. "
                    "Go to SMTP, add your mail servers, or import CSV with all mailboxes.",
                ],
            },
        )
    return get_default_smtp_server(owner) or servers[0]


def _email_domain(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].lower().strip()


def _resolve_from_email(campaign: Campaign, smtp_server: SmtpServer | None) -> str:
    # Always use the assigned sender mailbox when present (multi-sender safe).
    if smtp_server and smtp_server.from_email:
        return smtp_server.from_email.strip()
    if campaign.from_email and "gmail.com" not in _email_domain(campaign.from_email):
        return campaign.from_email.strip()
    if campaign.from_email:
        raise smtplib.SMTPException(
            "From email cannot be @gmail.com when sending via your domain SMTP. "
            "Use your mailbox address (e.g. info@yourdomain.com).",
        )
    return settings.DEFAULT_FROM_EMAIL


def _resolve_from_name(campaign: Campaign, smtp_server: SmtpServer | None) -> str:
    # Prefer each SMTP sender's own display name (Ava / Mia / …).
    if smtp_server:
        name = (smtp_server.from_name or "").strip()
        if name:
            return name
        label = (smtp_server.name or "").strip()
        # Human Sender-page labels when from_name is empty.
        if label and "@" not in label and (" " in label or label[:1].isupper()):
            return label
    if campaign and (campaign.from_name or "").strip():
        return campaign.from_name.strip()
    return ""


def _sender_display_names_for_swap(
    *,
    campaign: Campaign,
    smtp_server: SmtpServer | None,
) -> list[str]:
    """All known sender display names so hardcoded signatures can be rewritten."""
    names: list[str] = []
    seen: set[str] = set()

    def add(value: str | None):
        text = (value or "").strip()
        if len(text) < 2:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        names.append(text)

    try:
        for server in resolve_campaign_smtp_servers(campaign):
            add(server.from_name)
            if server.name and "@" not in server.name:
                add(server.name)
    except ValidationError:
        pass
    for server in get_active_smtp_servers(campaign.owner):
        add(server.from_name)
    add(getattr(campaign, "from_name", None))
    if smtp_server:
        add(smtp_server.from_name)
    # Longest first so "David Wilson" wins over "David".
    names.sort(key=len, reverse=True)
    return names


@transaction.atomic
def queue_campaign(*, campaign: Campaign, smtp_server: SmtpServer | None = None):
    _validate_campaign_for_send(campaign)

    servers = resolve_campaign_smtp_servers(campaign)
    if not servers:
        raise ValidationError(
            {
                "smtp": [
                    "No active SMTP servers. Add mailboxes under SMTP or Sender.",
                ],
            },
        )

    if smtp_server is None:
        smtp_server = get_default_smtp_server(campaign.owner) or servers[0]
    elif smtp_server.id not in {s.id for s in servers}:
        smtp_server = servers[0]

    recipients = _subscribed_recipients_in_list_order(campaign.subscriber_list)
    recipient_count = len(recipients)
    if recipient_count == 0:
        raise ValidationError(
            {
                "subscriber_list_id": [
                    "Email list has no active emails. "
                    "Go to Emails, select this list, and add emails first.",
                ],
            },
        )

    recipient_ids = [subscriber.id for subscriber in recipients]
    membership_added_at = _list_membership_added_at_by_subscriber(
        subscriber_list=campaign.subscriber_list,
    )
    already_sent_ids = _subscribers_sent_since_list_import(
        owner=campaign.owner,
        subscriber_list=campaign.subscriber_list,
        subscriber_ids=recipient_ids,
        membership_added_at=membership_added_at,
    )

    campaign.status = Campaign.Status.SENDING
    campaign.recipient_count = recipient_count
    campaign.save(update_fields=["status", "recipient_count", "updated_at"])

    emails_per_sender = getattr(campaign, "emails_per_sender", None) or 1
    cap = _campaign_batch_cap(campaign, servers)

    existing_by_subscriber = {
        item.subscriber_id: item
        for item in campaign.queue_items.select_related("subscriber")
    }

    waiting: list[Subscriber] = []
    for subscriber in recipients:
        if subscriber.id in already_sent_ids:
            EmailQueueItem.objects.get_or_create(
                campaign=campaign,
                subscriber=subscriber,
                defaults={
                    "owner": campaign.owner,
                    "smtp_server": servers[0],
                    "to_email": subscriber.email,
                    "status": EmailQueueItem.Status.SKIPPED,
                    "last_error": "Already sent previously — skipped.",
                },
            )
            continue
        if is_undeliverable_email(subscriber.email):
            EmailQueueItem.objects.get_or_create(
                campaign=campaign,
                subscriber=subscriber,
                defaults={
                    "owner": campaign.owner,
                    "smtp_server": servers[0],
                    "to_email": subscriber.email,
                    "status": EmailQueueItem.Status.SKIPPED,
                    "last_error": (
                        "Test/fake address (@example.com etc.) cannot receive mail. "
                        "Use a real Gmail address."
                    ),
                },
            )
            continue
        item = existing_by_subscriber.get(subscriber.id)
        if (
            item is not None
            and item.status == EmailQueueItem.Status.SENT
            and not _should_requeue_after_csv_reimport(
                queue_item=item,
                membership_added_at=membership_added_at,
            )
        ):
            continue
        waiting.append(subscriber)

    # Strict: only N × senders emails become PENDING this pass — never one extra.
    batch = waiting[:cap]
    remainder = waiting[cap:]
    allowed_ids = {subscriber.id for subscriber in batch}

    queued = 0
    for send_index, subscriber in enumerate(batch):
        assigned_server = _pick_smtp_server(servers, send_index, emails_per_sender)
        if assigned_server is None:
            _skip_over_send_limit(
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=servers[0],
                existing=existing_by_subscriber.get(subscriber.id),
            )
            continue

        item = existing_by_subscriber.get(subscriber.id)
        if item is None:
            EmailQueueItem.objects.create(
                owner=campaign.owner,
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=assigned_server,
                to_email=subscriber.email,
                status=EmailQueueItem.Status.PENDING,
            )
            queued += 1
            continue

        item.status = EmailQueueItem.Status.PENDING
        item.last_error = ""
        item.smtp_server = assigned_server
        item.to_email = subscriber.email
        item.sent_at = None
        item.save(
            update_fields=[
                "status",
                "last_error",
                "smtp_server",
                "to_email",
                "sent_at",
                "updated_at",
            ],
        )
        queued += 1

    for subscriber in remainder:
        _skip_over_send_limit(
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=servers[0],
            existing=existing_by_subscriber.get(subscriber.id),
        )

    _demote_excess_pending(
        campaign=campaign,
        allowed_subscriber_ids=allowed_ids,
        smtp_server=servers[0],
    )

    return queued


@transaction.atomic
def requeue_campaign_items(*, campaign: Campaign):
    """Reset failed/pending items within the strict N×senders cap for this pass."""
    _validate_campaign_for_send(campaign, allow_sending=True)

    servers = resolve_campaign_smtp_servers(campaign)
    if not servers:
        raise ValidationError(
            {"smtp": ["No active SMTP servers configured."]},
        )

    recipients = _subscribed_recipients_in_list_order(campaign.subscriber_list)
    campaign.recipient_count = len(recipients)
    campaign.save(update_fields=["recipient_count", "updated_at"])

    membership_added_at = _list_membership_added_at_by_subscriber(
        subscriber_list=campaign.subscriber_list,
    )
    already_sent_ids = _subscribers_sent_since_list_import(
        owner=campaign.owner,
        subscriber_list=campaign.subscriber_list,
        subscriber_ids=[subscriber.id for subscriber in recipients],
        membership_added_at=membership_added_at,
    )

    waiting = [
        subscriber
        for subscriber in recipients
        if subscriber.id not in already_sent_ids
        and not is_undeliverable_email(subscriber.email)
    ]
    emails_per_sender = getattr(campaign, "emails_per_sender", None) or 1
    cap = _campaign_batch_cap(campaign, servers)
    batch = waiting[:cap]
    remainder = waiting[cap:]
    allowed_ids = {subscriber.id for subscriber in batch}

    existing_by_subscriber = {
        item.subscriber_id: item
        for item in campaign.queue_items.select_related("subscriber")
    }
    requeued = 0

    for send_index, subscriber in enumerate(batch):
        assigned_server = _pick_smtp_server(servers, send_index, emails_per_sender)
        if assigned_server is None:
            _skip_over_send_limit(
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=servers[0],
                existing=existing_by_subscriber.get(subscriber.id),
            )
            continue

        item = existing_by_subscriber.get(subscriber.id)
        if item is None:
            EmailQueueItem.objects.create(
                owner=campaign.owner,
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=assigned_server,
                to_email=subscriber.email,
                status=EmailQueueItem.Status.PENDING,
            )
            requeued += 1
            continue

        if item.status == EmailQueueItem.Status.SENT:
            continue

        item.smtp_server = assigned_server
        item.status = EmailQueueItem.Status.PENDING
        item.last_error = ""
        item.save(
            update_fields=["smtp_server", "status", "last_error", "updated_at"],
        )
        requeued += 1

    for subscriber in remainder:
        _skip_over_send_limit(
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=servers[0],
            existing=existing_by_subscriber.get(subscriber.id),
        )

    _demote_excess_pending(
        campaign=campaign,
        allowed_subscriber_ids=allowed_ids,
        smtp_server=servers[0],
    )

    if campaign.status != Campaign.Status.SENDING:
        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=["status", "updated_at"])

    return requeued


@transaction.atomic
def extend_campaign_for_send(*, campaign: Campaign) -> int:
    """
    Resume / Send Again: queue the next N×senders of still-waiting list emails.

    Already-sent rows are skipped; next rows get the next sender batch, then stop
    again until the user resumes.
    """
    servers = resolve_campaign_smtp_servers(campaign)
    if not servers:
        raise ValidationError(
            {"smtp": ["No active SMTP servers configured."]},
        )

    recipients = _subscribed_recipients_in_list_order(campaign.subscriber_list)
    recipient_ids = [subscriber.id for subscriber in recipients]
    membership_added_at = _list_membership_added_at_by_subscriber(
        subscriber_list=campaign.subscriber_list,
    )
    already_sent_ids = _subscribers_sent_since_list_import(
        owner=campaign.owner,
        subscriber_list=campaign.subscriber_list,
        subscriber_ids=recipient_ids,
        membership_added_at=membership_added_at,
    )

    waiting = [
        subscriber
        for subscriber in recipients
        if subscriber.id not in already_sent_ids
        and not is_undeliverable_email(subscriber.email)
    ]
    if not waiting:
        return 0

    emails_per_sender = getattr(campaign, "emails_per_sender", None) or 1
    batch_size = _campaign_batch_cap(campaign, servers)
    batch = waiting[:batch_size]
    remainder = waiting[batch_size:]
    allowed_ids = {subscriber.id for subscriber in batch}

    existing_by_subscriber = {
        item.subscriber_id: item
        for item in campaign.queue_items.select_related("subscriber")
    }

    pending_added = 0
    for send_index, subscriber in enumerate(batch):
        assigned_server = _pick_smtp_server(servers, send_index, emails_per_sender)
        if assigned_server is None:
            _skip_over_send_limit(
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=servers[0],
                existing=existing_by_subscriber.get(subscriber.id),
            )
            continue

        item = existing_by_subscriber.get(subscriber.id)
        if item is None:
            EmailQueueItem.objects.create(
                owner=campaign.owner,
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=assigned_server,
                to_email=subscriber.email,
                status=EmailQueueItem.Status.PENDING,
            )
            pending_added += 1
            continue

        if item.status == EmailQueueItem.Status.SENT:
            continue

        item.smtp_server = assigned_server
        item.status = EmailQueueItem.Status.PENDING
        item.last_error = ""
        item.sent_at = None
        item.save(
            update_fields=[
                "smtp_server",
                "status",
                "last_error",
                "sent_at",
                "updated_at",
            ],
        )
        pending_added += 1

    for subscriber in remainder:
        _skip_over_send_limit(
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=servers[0],
            existing=existing_by_subscriber.get(subscriber.id),
        )

    _demote_excess_pending(
        campaign=campaign,
        allowed_subscriber_ids=allowed_ids,
        smtp_server=servers[0],
    )

    for subscriber in recipients:
        if subscriber.id in already_sent_ids:
            continue
        if not is_undeliverable_email(subscriber.email):
            continue
        item = existing_by_subscriber.get(subscriber.id)
        if item is not None:
            continue
        EmailQueueItem.objects.create(
            owner=campaign.owner,
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=servers[0],
            to_email=subscriber.email,
            status=EmailQueueItem.Status.SKIPPED,
            last_error=(
                "Test/fake address (@example.com etc.) cannot receive mail. "
                "Use a real Gmail address."
            ),
        )

    if pending_added > 0:
        campaign.status = Campaign.Status.SENDING
        campaign.recipient_count = len(recipients)
        campaign.sent_at = None
        campaign.save(
            update_fields=["status", "recipient_count", "sent_at", "updated_at"],
        )

    return pending_added


def send_campaign_test_email(*, campaign: Campaign, to_email: str):
    """Send one preview email immediately (not via the queue) to any real inbox."""
    to_email = (to_email or "").strip().lower()
    if not to_email or "@" not in to_email:
        raise ValidationError({"to_email": ["Enter a valid email address."]})
    if is_undeliverable_email(to_email):
        raise ValidationError(
            {"to_email": ["Use a real email address (Gmail is OK), not @example.com."]},
        )

    servers = resolve_campaign_smtp_servers(campaign)
    smtp_server = servers[0] if servers else _validate_smtp_configured(campaign.owner)
    from_email = _resolve_from_email(campaign, smtp_server)
    from_name = _resolve_from_name(campaign, smtp_server)
    swap_names = _sender_display_names_for_swap(
        campaign=campaign,
        smtp_server=smtp_server,
    )

    subscriber = None
    if campaign.subscriber_list_id:
        subscriber = campaign.subscriber_list.subscribers.filter(email=to_email).first()
        if subscriber is None:
            recipients = _subscribed_recipients_in_list_order(campaign.subscriber_list)
            subscriber = recipients[0] if recipients else None
    html_content = _personalize(
        campaign.html_content,
        subscriber,
        sender_name=from_name,
        sender_email=from_email,
        sender_names_to_swap=swap_names,
    )
    text_content = _personalize(
        campaign.text_content,
        subscriber,
        sender_name=from_name,
        sender_email=from_email,
        sender_names_to_swap=swap_names,
    )
    subject = _personalize(
        campaign.subject,
        subscriber,
        sender_name=from_name,
        sender_email=from_email,
        sender_names_to_swap=swap_names,
    )
    if not subject:
        subject = campaign.subject or campaign.name
    html_content = _format_html_message(html_content)

    try:
        send_message_via_smtp(
            smtp_server=smtp_server,
            to_email=to_email,
            subject=f"[Test] {subject}",
            html_content=html_content,
            text_content=text_content,
            from_email=from_email,
            from_name=from_name,
            # Test must not wait on IMAP Sent-folder sync (often times out on shared hosts).
            save_to_sent=False,
        )
    except smtplib.SMTPException as exc:
        raise ValidationError(
            {"to_email": [f"SMTP could not send test email: {exc}"]},
        ) from exc
    except OSError as exc:
        raise ValidationError(
            {"to_email": [f"Could not connect to SMTP: {exc}"]},
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surface any unexpected send failure to UI
        raise ValidationError(
            {"to_email": [f"Test email failed: {exc}"]},
        ) from exc
    return {"to_email": to_email, "from_email": from_email}


def process_queue_item(*, queue_item: EmailQueueItem):
    if queue_item.status == EmailQueueItem.Status.SENT:
        return True

    campaign = queue_item.campaign
    campaign.refresh_from_db()
    # Stop pressed: do not send; keep item pending for Resume.
    if campaign.status != Campaign.Status.SENDING:
        if queue_item.status == EmailQueueItem.Status.SENDING:
            queue_item.status = EmailQueueItem.Status.PENDING
            queue_item.save(update_fields=["status", "updated_at"])
        return False

    subscriber = queue_item.subscriber

    if subscriber.status != Subscriber.Status.SUBSCRIBED:
        queue_item.status = EmailQueueItem.Status.SKIPPED
        queue_item.last_error = "Subscriber is not subscribed."
        queue_item.save(update_fields=["status", "last_error", "updated_at"])
        return False

    if is_undeliverable_email(queue_item.to_email):
        queue_item.status = EmailQueueItem.Status.SKIPPED
        queue_item.last_error = (
            "Test/fake address (@example.com etc.) cannot receive mail. "
            "Use a real Gmail address."
        )
        queue_item.save(update_fields=["status", "last_error", "updated_at"])
        return False

    campaign_id = str(campaign.id)

    queue_item.status = EmailQueueItem.Status.SENDING
    queue_item.attempts += 1
    queue_item.save(update_fields=["status", "attempts", "updated_at"])

    try:
        smtp_server = queue_item.smtp_server or get_default_smtp_server(campaign.owner)
        if not smtp_server or not smtp_server.is_active:
            raise smtplib.SMTPException(
                "No active SMTP server. Configure SMTP and set a default server.",
            )

        from_email = _resolve_from_email(campaign, smtp_server)
        from_name = _resolve_from_name(campaign, smtp_server)
        swap_names = _sender_display_names_for_swap(
            campaign=campaign,
            smtp_server=smtp_server,
        )

        html_content = _personalize(
            campaign.html_content,
            subscriber,
            sender_name=from_name,
            sender_email=from_email,
            sender_names_to_swap=swap_names,
        )
        text_content = _personalize(
            campaign.text_content,
            subscriber,
            sender_name=from_name,
            sender_email=from_email,
            sender_names_to_swap=swap_names,
        )
        subject = _personalize(
            campaign.subject,
            subscriber,
            sender_name=from_name,
            sender_email=from_email,
            sender_names_to_swap=swap_names,
        )

        from tracking.context import set_campaign_tracking_base_url
        from tracking.services import resolve_send_tracking_base_url

        tracking_base_url = resolve_send_tracking_base_url(
            campaign_id=campaign_id,
            from_email=from_email,
        ) or get_tracking_base_url(campaign_id)
        if tracking_base_url:
            set_campaign_tracking_base_url(campaign_id, tracking_base_url)

        html_content = inject_open_tracking_pixel(
            _format_html_message(html_content),
            str(queue_item.id),
            campaign_id=campaign_id,
            from_email=from_email,
        )
        text_content = append_text_tracking_link(
            text_content,
            str(queue_item.id),
            campaign_id=campaign_id,
        )

        send_message_via_smtp(
            smtp_server=smtp_server,
            to_email=queue_item.to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_email=from_email,
            from_name=from_name,
        )

        queue_item.status = EmailQueueItem.Status.SENT
        queue_item.sent_at = timezone.now()
        queue_item.last_error = ""
        queue_item.save(update_fields=["status", "sent_at", "last_error", "updated_at"])

        TrackingEvent.objects.create(
            owner=campaign.owner,
            campaign=campaign,
            subscriber=subscriber,
            event_type=TrackingEvent.EventType.SENT,
            metadata={"queue_item_id": str(queue_item.id)},
        )
        TrackingEvent.objects.create(
            owner=campaign.owner,
            campaign=campaign,
            subscriber=subscriber,
            event_type=TrackingEvent.EventType.DELIVERED,
            metadata={
                "queue_item_id": str(queue_item.id),
                "to_email": queue_item.to_email,
                "tracking_base_url": tracking_base_url,
            },
        )
        return True
    except Exception as exc:
        logger.exception("Failed to send queue item %s", queue_item.id)
        queue_item.status = EmailQueueItem.Status.FAILED
        queue_item.last_error = str(exc)[:500]
        queue_item.save(update_fields=["status", "last_error", "updated_at"])
        return False


def get_campaign_send_summary(campaign: Campaign) -> dict:
    items = campaign.queue_items.all()
    failed_items = items.filter(status=EmailQueueItem.Status.FAILED)
    pending = items.filter(status=EmailQueueItem.Status.PENDING).count()
    try:
        active_servers = resolve_campaign_smtp_servers(campaign)
    except ValidationError:
        active_servers = get_active_smtp_servers(campaign.owner)
    smtp_server = active_servers[0] if active_servers else get_default_smtp_server(campaign.owner)
    per_server_interval = (
        compute_send_interval_seconds(smtp_server) if smtp_server else MIN_SEND_INTERVAL_SECONDS
    )
    parallel = max(len(active_servers), 1)
    effective_interval = max(MIN_SEND_INTERVAL_SECONDS, per_server_interval // parallel)
    next_in = get_next_send_in_seconds(smtp_server=smtp_server) if pending else 0
    return {
        "total": items.count(),
        "pending": pending,
        "sent": items.filter(status=EmailQueueItem.Status.SENT).count(),
        "failed": failed_items.count(),
        "skipped": items.filter(status=EmailQueueItem.Status.SKIPPED).count(),
        "send_interval_seconds": effective_interval,
        "next_send_in_seconds": next_in,
        "active_smtp_servers": parallel,
        "is_rate_limited": campaign.status == Campaign.Status.SENDING and pending > 0,
        "errors": [
            {"email": item.to_email, "error": item.last_error}
            for item in failed_items.order_by("-updated_at")[:10]
        ],
    }


def finalize_campaign_if_complete(*, campaign: Campaign):
    pending = campaign.queue_items.filter(
        status__in=[EmailQueueItem.Status.PENDING, EmailQueueItem.Status.SENDING],
    ).exists()
    if pending:
        return campaign

    if campaign.status == Campaign.Status.SENDING:
        campaign.status = Campaign.Status.SENT
        campaign.sent_at = timezone.now()
        campaign.save(update_fields=["status", "sent_at", "updated_at"])
    return campaign


def get_pending_queue_item_ids(campaign_id):
    return list(
        EmailQueueItem.objects.filter(
            campaign_id=campaign_id,
            status=EmailQueueItem.Status.PENDING,
        ).values_list("id", flat=True),
    )


def get_due_scheduled_campaigns():
    return Campaign.objects.filter(
        status=Campaign.Status.SCHEDULED,
        scheduled_at__lte=timezone.now(),
    )
