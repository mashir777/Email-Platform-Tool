import email
import imaplib
import logging
import re
from datetime import timezone as dt_timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from django.utils import timezone

from core.encryption import decrypt_value, encrypt_value
from inbox.models import InboxMailbox, InboxMessage
from smtp_servers.connection import create_smtp_ssl_context

logger = logging.getLogger(__name__)


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return (raw or "").strip()


def _extract_body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()
        for part in msg.walk():
            if (part.get_content_type() or "").lower() == "text/html":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace")
                text = re.sub(r"<[^>]+>", " ", html)
                return re.sub(r"\s+", " ", text).strip()
        return ""
    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace").strip()


def _parse_received_at(msg: email.message.Message):
    raw = msg.get("Date")
    if not raw:
        return timezone.now()
    try:
        dt = parsedate_to_datetime(raw)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, dt_timezone.utc)
        return dt
    except Exception:
        return timezone.now()


def create_inbox_mailbox(
    *,
    owner,
    email: str,
    imap_host: str,
    username: str,
    password: str,
    name: str = "",
    imap_port: int = 993,
    verify_ssl: bool = False,
) -> InboxMailbox:
    email_norm = (email or "").strip().lower()
    if InboxMailbox.objects.filter(owner=owner, email=email_norm).exists():
        from django.core.exceptions import ValidationError

        raise ValidationError({"email": ["This inbox is already added."]})
    return InboxMailbox.objects.create(
        owner=owner,
        name=(name or email_norm).strip()[:255],
        email=email_norm,
        imap_host=(imap_host or "").strip(),
        imap_port=imap_port or 993,
        username=(username or email_norm).strip(),
        password_encrypted=encrypt_value(password),
        verify_ssl=bool(verify_ssl),
        is_active=True,
    )


def sync_inbox_mailbox(*, mailbox: InboxMailbox, limit: int = 50) -> int:
    """Fetch recent INBOX messages for a Unibox mailbox."""
    if not mailbox.username or not mailbox.password_encrypted:
        return 0
    password = decrypt_value(mailbox.password_encrypted)
    if not password:
        return 0

    host = (mailbox.imap_host or "").strip()
    port = mailbox.imap_port or 993
    context = create_smtp_ssl_context(verify_ssl=mailbox.verify_ssl)
    created = 0
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(host, port, ssl_context=context)
        mail.login(mailbox.username, password)
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            mailbox.last_synced_at = timezone.now()
            mailbox.last_sync_message = "Could not open INBOX."
            mailbox.save(update_fields=["last_synced_at", "last_sync_message", "updated_at"])
            return 0
        status, data = mail.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            mailbox.last_synced_at = timezone.now()
            mailbox.last_sync_message = "INBOX empty."
            mailbox.save(update_fields=["last_synced_at", "last_sync_message", "updated_at"])
            return 0
        uids = data[0].split()
        for uid in uids[-limit:]:
            uid_str = uid.decode("ascii", errors="replace")
            if InboxMessage.objects.filter(
                owner=mailbox.owner,
                mailbox=mailbox,
                imap_uid=uid_str,
            ).exists():
                continue
            status, fetched = mail.fetch(uid, "(RFC822)")
            if status != "OK" or not fetched or not fetched[0]:
                continue
            raw = fetched[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(raw)
            from_name, from_email = parseaddr(msg.get("From", ""))
            _, to_email = parseaddr(msg.get("To", ""))
            subject = _decode_header_value(msg.get("Subject"))
            body = _extract_body_text(msg)
            snippet = (body or subject)[:500]
            message_id = (msg.get("Message-ID") or "").strip()[:512]
            InboxMessage.objects.create(
                owner=mailbox.owner,
                mailbox=mailbox,
                mailbox_email=mailbox.email,
                message_id=message_id,
                imap_uid=uid_str,
                from_email=(from_email or "")[:254],
                from_name=_decode_header_value(from_name)[:255],
                to_email=(to_email or mailbox.email)[:254],
                subject=subject[:998],
                snippet=snippet,
                body_text=body[:20000],
                received_at=_parse_received_at(msg),
                is_read=False,
            )
            created += 1
        mailbox.last_synced_at = timezone.now()
        mailbox.last_sync_message = f"OK — {created} new."
        mailbox.save(update_fields=["last_synced_at", "last_sync_message", "updated_at"])
        return created
    except Exception as exc:
        logger.warning(
            "Unibox IMAP sync failed for %s (%s)",
            mailbox.email,
            host,
            exc_info=True,
        )
        mailbox.last_synced_at = timezone.now()
        mailbox.last_sync_message = str(exc)[:500]
        mailbox.save(update_fields=["last_synced_at", "last_sync_message", "updated_at"])
        return 0
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass


def sync_owner_inboxes(*, owner, limit_per_mailbox: int = 40) -> dict:
    """Sync Unibox-added mailboxes (primary source for replies in the app)."""
    mailboxes = InboxMailbox.objects.filter(owner=owner, is_active=True)
    total = 0
    synced = 0
    for mailbox in mailboxes:
        count = sync_inbox_mailbox(mailbox=mailbox, limit=limit_per_mailbox)
        synced += 1
        total += count
    return {"mailboxes": synced, "new_messages": total}
