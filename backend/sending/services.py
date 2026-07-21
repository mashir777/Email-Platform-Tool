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

MIN_SEND_INTERVAL_SECONDS = 60


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


def compute_send_interval_seconds(smtp_server: SmtpServer) -> int:
    """Seconds between consecutive sends based on hourly limit (minimum 60s)."""
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
    if (
        _count_sent_since(smtp_server_id=smtp_server.id, since=now - timedelta(days=1))
        >= smtp_server.daily_limit
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
    qs = EmailQueueItem.objects.filter(
        status=EmailQueueItem.Status.PENDING,
        campaign__status=Campaign.Status.SENDING,
    ).select_related("campaign", "subscriber", "smtp_server")
    if smtp_server_id:
        qs = qs.filter(smtp_server_id=smtp_server_id)
    return qs.order_by("created_at").first()


def has_pending_queue_items() -> bool:
    return EmailQueueItem.objects.filter(
        status=EmailQueueItem.Status.PENDING,
        campaign__status=Campaign.Status.SENDING,
    ).exists()


def run_pending_email_queue() -> dict:
    """Send one pending email per SMTP server that is allowed to send."""
    processed = 0
    for server in SmtpServer.objects.filter(is_active=True).iterator():
        if not can_send_email(smtp_server=server):
            continue
        item = get_next_pending_queue_item(smtp_server_id=server.id)
        if not item:
            continue
        process_queue_item(queue_item=item)
        finalize_campaign_if_complete(campaign=item.campaign)
        processed += 1

    if processed == 0:
        item = (
            EmailQueueItem.objects.filter(
                status=EmailQueueItem.Status.PENDING,
                campaign__status=Campaign.Status.SENDING,
            )
            .select_related("campaign", "subscriber", "smtp_server")
            .order_by("created_at")
            .first()
        )
        if item:
            smtp_server = item.smtp_server or get_default_smtp_server(item.campaign.owner)
            if smtp_server and can_send_email(smtp_server=smtp_server):
                if not item.smtp_server_id:
                    item.smtp_server = smtp_server
                    item.save(update_fields=["smtp_server", "updated_at"])
                process_queue_item(queue_item=item)
                finalize_campaign_if_complete(campaign=item.campaign)
                processed += 1

    return {"processed": processed}


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


def _pick_smtp_server(servers: list[SmtpServer], index: int) -> SmtpServer:
    return servers[index % len(servers)]


def _personalize(content: str, subscriber: Subscriber) -> str:
    if not content:
        return ""
    display_name = subscriber.full_name or subscriber.first_name or ""
    company = getattr(subscriber, "company", "") or ""
    industrial_company = getattr(subscriber, "industrial_company", "") or ""

    def normalize_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    fields = {
        normalize_key(key): str(value or "")
        for key, value in (subscriber.custom_fields or {}).items()
    }
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
        if value or key not in fields:
            fields[key] = value

    placeholder_pattern = re.compile(
        r"\{\{\s*([^{}]+?)\s*\}\}|\[([^\[\]]+?)\]",
    )

    def replace_placeholder(match):
        raw_key = match.group(1) or match.group(2) or ""
        normalized = normalize_key(raw_key)
        return fields.get(normalized, match.group(0))

    return placeholder_pattern.sub(replace_placeholder, content)


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


def send_message_via_smtp(
    *,
    smtp_server: SmtpServer,
    to_email: str,
    subject: str,
    html_content: str = "",
    text_content: str = "",
    from_email: str = "",
    from_name: str = "",
):
    sender_email = from_email or smtp_server.from_email
    sender_name = from_name or smtp_server.from_name
    from_header = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_header
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender_email.split("@")[-1] if "@" in sender_email else None)
    message["Reply-To"] = sender_email
    # MIMEMultipart already sets MIME-Version; setting it again makes a duplicate
    # header that AWS SES rejects with 554 "Duplicate header 'MIME-Version'".

    body_text = text_content or "This email requires an HTML-capable client."
    message.attach(MIMEText(body_text, "plain", "utf-8"))
    if html_content:
        message.attach(MIMEText(html_content, "html", "utf-8"))

    with connect_smtp_server(smtp_server=smtp_server) as server:
        envelope_from = (from_email or smtp_server.from_email).strip()
        server.sendmail(envelope_from, [to_email], message.as_string())

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
    if smtp_server and smtp_server.from_email:
        smtp_domain = _email_domain(smtp_server.from_email)
        if campaign.from_email:
            campaign_domain = _email_domain(campaign.from_email)
            if campaign_domain == smtp_domain:
                return campaign.from_email.strip()
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
    if campaign.from_name:
        return campaign.from_name
    if smtp_server and smtp_server.from_name:
        return smtp_server.from_name
    return ""


@transaction.atomic
def queue_campaign(*, campaign: Campaign, smtp_server: SmtpServer | None = None):
    _validate_campaign_for_send(campaign)

    servers = get_active_smtp_servers(campaign.owner)
    if not servers:
        raise ValidationError(
            {
                "smtp": [
                    "No active SMTP servers. Add mailboxes under SMTP or import CSV.",
                ],
            },
        )

    if smtp_server is None:
        smtp_server = get_default_smtp_server(campaign.owner) or servers[0]

    recipients = campaign.subscriber_list.subscribers.filter(
        status=Subscriber.Status.SUBSCRIBED,
    )
    recipient_count = recipients.count()
    if recipient_count == 0:
        raise ValidationError(
            {
                "subscriber_list_id": [
                    "Email list has no active emails. "
                    "Go to Emails, select this list, and add emails first.",
                ],
            },
        )

    recipient_ids = list(recipients.values_list("id", flat=True))
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

    queued = 0
    for index, subscriber in enumerate(recipients.iterator()):
        assigned_server = _pick_smtp_server(servers, index)
        if subscriber.id in already_sent_ids:
            EmailQueueItem.objects.get_or_create(
                campaign=campaign,
                subscriber=subscriber,
                defaults={
                    "owner": campaign.owner,
                    "smtp_server": assigned_server,
                    "to_email": subscriber.email,
                    "status": EmailQueueItem.Status.SKIPPED,
                    "last_error": "Already sent previously — skipped.",
                },
            )
            continue

        item, was_created = EmailQueueItem.objects.get_or_create(
            campaign=campaign,
            subscriber=subscriber,
            defaults={
                "owner": campaign.owner,
                "smtp_server": assigned_server,
                "to_email": subscriber.email,
                "status": EmailQueueItem.Status.PENDING,
            },
        )
        if was_created:
            queued += 1
            continue

        updates = []
        if item.status in {
            EmailQueueItem.Status.FAILED,
            EmailQueueItem.Status.SKIPPED,
        }:
            if subscriber.id in already_sent_ids:
                continue
            item.status = EmailQueueItem.Status.PENDING
            item.last_error = ""
            updates.extend(["status", "last_error"])
        elif item.status == EmailQueueItem.Status.SENT:
            if _should_requeue_after_csv_reimport(
                queue_item=item,
                membership_added_at=membership_added_at,
            ):
                item.status = EmailQueueItem.Status.PENDING
                item.last_error = ""
                item.sent_at = None
                updates.extend(["status", "last_error", "sent_at"])
                queued += 1
            continue
        if item.smtp_server_id != assigned_server.id:
            item.smtp_server = assigned_server
            updates.append("smtp_server")
        if item.to_email != subscriber.email:
            item.to_email = subscriber.email
            updates.append("to_email")
        if updates:
            item.save(update_fields=[*updates, "updated_at"])

    return queued


@transaction.atomic
def requeue_campaign_items(*, campaign: Campaign):
    """Reset failed/pending items and reassign SMTP servers (round-robin)."""
    _validate_campaign_for_send(campaign, allow_sending=True)

    servers = get_active_smtp_servers(campaign.owner)
    if not servers:
        raise ValidationError(
            {"smtp": ["No active SMTP servers configured."]},
        )

    recipients = campaign.subscriber_list.subscribers.filter(
        status=Subscriber.Status.SUBSCRIBED,
    )
    campaign.recipient_count = recipients.count()
    campaign.save(update_fields=["recipient_count", "updated_at"])

    existing_subscriber_ids = set(
        campaign.queue_items.values_list("subscriber_id", flat=True),
    )
    for index, subscriber in enumerate(recipients.iterator()):
        if subscriber.id in existing_subscriber_ids:
            continue
        assigned_server = _pick_smtp_server(servers, index)
        EmailQueueItem.objects.create(
            owner=campaign.owner,
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=assigned_server,
            to_email=subscriber.email,
            status=EmailQueueItem.Status.PENDING,
        )

    items = campaign.queue_items.filter(
        status__in=[
            EmailQueueItem.Status.PENDING,
            EmailQueueItem.Status.FAILED,
        ],
    ).order_by("created_at")

    for index, item in enumerate(items):
        assigned_server = _pick_smtp_server(servers, index)
        item.smtp_server = assigned_server
        item.status = EmailQueueItem.Status.PENDING
        item.last_error = ""
        item.save(
            update_fields=["smtp_server", "status", "last_error", "updated_at"],
        )

    if campaign.status != Campaign.Status.SENDING:
        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=["status", "updated_at"])

    return items.count()


@transaction.atomic
def extend_campaign_for_send(*, campaign: Campaign) -> int:
    """Re-open a sent campaign when new real subscribers were added to the list."""
    servers = get_active_smtp_servers(campaign.owner)
    if not servers:
        raise ValidationError(
            {"smtp": ["No active SMTP servers configured."]},
        )

    recipients = campaign.subscriber_list.subscribers.filter(
        status=Subscriber.Status.SUBSCRIBED,
    )
    recipient_ids = list(recipients.values_list("id", flat=True))
    membership_added_at = _list_membership_added_at_by_subscriber(
        subscriber_list=campaign.subscriber_list,
    )
    existing_subscriber_ids = set(
        campaign.queue_items.values_list("subscriber_id", flat=True),
    )
    already_sent_ids = _subscribers_sent_since_list_import(
        owner=campaign.owner,
        subscriber_list=campaign.subscriber_list,
        subscriber_ids=recipient_ids,
        membership_added_at=membership_added_at,
    )

    pending_added = 0
    for index, item in enumerate(
        campaign.queue_items.select_related("subscriber").order_by("created_at"),
    ):
        if not _should_requeue_after_csv_reimport(
            queue_item=item,
            membership_added_at=membership_added_at,
        ):
            continue
        if item.subscriber_id in already_sent_ids:
            continue
        assigned_server = _pick_smtp_server(servers, index)
        _requeue_item_for_resend(queue_item=item, assigned_server=assigned_server)
        pending_added += 1

    for index, subscriber in enumerate(recipients.iterator()):
        if subscriber.id in existing_subscriber_ids:
            continue
        assigned_server = _pick_smtp_server(servers, index)
        if subscriber.id in already_sent_ids:
            EmailQueueItem.objects.create(
                owner=campaign.owner,
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=assigned_server,
                to_email=subscriber.email,
                status=EmailQueueItem.Status.SKIPPED,
                last_error="Already sent previously — skipped.",
            )
            continue
        if is_undeliverable_email(subscriber.email):
            EmailQueueItem.objects.create(
                owner=campaign.owner,
                campaign=campaign,
                subscriber=subscriber,
                smtp_server=assigned_server,
                to_email=subscriber.email,
                status=EmailQueueItem.Status.SKIPPED,
                last_error=(
                    "Test/fake address (@example.com etc.) cannot receive mail. "
                    "Use a real Gmail address."
                ),
            )
            continue

        EmailQueueItem.objects.create(
            owner=campaign.owner,
            campaign=campaign,
            subscriber=subscriber,
            smtp_server=assigned_server,
            to_email=subscriber.email,
            status=EmailQueueItem.Status.PENDING,
        )
        pending_added += 1

    if pending_added > 0:
        campaign.status = Campaign.Status.SENDING
        campaign.recipient_count = recipients.count()
        campaign.save(update_fields=["status", "recipient_count", "updated_at"])

    return pending_added


def send_campaign_test_email(*, campaign: Campaign, to_email: str):
    """Send one preview email immediately (not via the queue)."""
    from campaigns.services import _validate_from_email_for_owner

    to_email = to_email.strip().lower()
    if is_undeliverable_email(to_email):
        raise ValidationError(
            {"to_email": ["Use a real email address (Gmail is OK), not @example.com."]},
        )

    smtp_server = _validate_smtp_configured(campaign.owner)
    from_email = _resolve_from_email(campaign, smtp_server)
    from_name = _resolve_from_name(campaign, smtp_server)
    _validate_from_email_for_owner(owner=campaign.owner, from_email=from_email)

    subscriber = (
        campaign.subscriber_list.subscribers.filter(email=to_email).first()
        if campaign.subscriber_list_id
        else None
    )
    if subscriber:
        html_content = _personalize(campaign.html_content, subscriber)
        text_content = _personalize(campaign.text_content, subscriber)
        subject = _personalize(campaign.subject, subscriber)
    else:
        html_content = campaign.html_content or ""
        text_content = campaign.text_content or ""
        subject = campaign.subject or campaign.name
    html_content = _format_html_message(html_content)

    send_message_via_smtp(
        smtp_server=smtp_server,
        to_email=to_email,
        subject=f"[Test] {subject}",
        html_content=html_content,
        text_content=text_content,
        from_email=from_email,
        from_name=from_name,
    )
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

    html_content = _personalize(campaign.html_content, subscriber)
    text_content = _personalize(campaign.text_content, subscriber)
    subject = _personalize(campaign.subject, subscriber)
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
