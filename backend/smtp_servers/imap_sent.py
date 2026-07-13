import imaplib
import logging
import re
import time
from email.utils import formatdate, make_msgid

from core.encryption import decrypt_value
from smtp_servers.connection import create_smtp_ssl_context
from smtp_servers.models import SmtpServer

logger = logging.getLogger(__name__)


def _parse_mailbox_name(line: bytes) -> str | None:
    if not line:
        return None
    text = line.decode("utf-8", errors="replace")
    match = re.search(r'"\."\s+(.+)$', text)
    if match:
        name = match.group(1).strip()
        if name and name != ".":
            return name
    match = re.search(r'"([^"]+)"\s*$', text)
    if match and match.group(1) != ".":
        return match.group(1)
    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


def _sent_folder_candidates(folders: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add(name: str):
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)

    for folder in folders:
        lower = folder.lower()
        if lower in {"sent", "sent items", "sent messages", "inbox.sent"}:
            add(folder)

    for folder in folders:
        lower = folder.lower()
        if lower.endswith(".sent") or lower.endswith("/sent"):
            add(folder)

    for folder in folders:
        lower = folder.lower()
        if "sent" in lower and "draft" not in lower and "unsent" not in lower:
            add(folder)

    for fallback in ("INBOX.Sent", "Sent", "INBOX/Sent", "Sent Items"):
        add(fallback)

    return ordered


def _append_to_sent_folder(mail: imaplib.IMAP4_SSL, *, folders: list[str], raw: bytes) -> bool:
    for folder in folders:
        status, response = mail.append(
            folder,
            "\\Seen",
            imaplib.Time2Internaldate(time.time()),
            raw,
        )
        if status == "OK":
            logger.info("Saved sent copy to %s", folder)
            return True
        logger.debug("IMAP APPEND to %s failed: %s %s", folder, status, response)
    return False


def _imap_host(smtp_server: SmtpServer) -> str:
    return (smtp_server.imap_host or smtp_server.host).strip()


def save_message_to_sent_folder(*, smtp_server: SmtpServer, message) -> bool:
    """Append a copy to the mailbox Sent folder (Namecheap / cPanel webmail)."""
    if not smtp_server.save_copy_to_sent:
        return False
    if not smtp_server.username:
        logger.debug("Skipping Sent folder save: no mailbox username configured.")
        return False

    password = decrypt_value(smtp_server.password_encrypted)
    if not password:
        logger.debug("Skipping Sent folder save: no mailbox password configured.")
        return False

    if "Date" not in message:
        message["Date"] = formatdate(localtime=True)
    if "Message-ID" not in message:
        domain = (smtp_server.from_email or "localhost").split("@")[-1]
        message["Message-ID"] = make_msgid(domain=domain)

    host = _imap_host(smtp_server)
    port = smtp_server.imap_port or 993
    raw = message.as_bytes()
    context = create_smtp_ssl_context(verify_ssl=smtp_server.verify_ssl)

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(host, port, ssl_context=context)
        mail.login(smtp_server.username, password)
        status, data = mail.list()
        folders: list[str] = []
        if status == "OK" and data:
            for item in data:
                name = _parse_mailbox_name(item)
                if name and name.upper() != "INBOX":
                    folders.append(name)
        sent_folders = _sent_folder_candidates(folders)
        if not _append_to_sent_folder(mail, folders=sent_folders, raw=raw):
            logger.warning(
                "IMAP APPEND failed for all Sent folder candidates on %s: %s",
                host,
                sent_folders,
            )
            return False
        return True
    except Exception:
        logger.warning("Could not save sent copy to mailbox %s", host, exc_info=True)
        return False
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass
