import logging
import smtplib
import ssl
import time

from core.encryption import decrypt_value
from smtp_servers.models import SmtpServer

logger = logging.getLogger(__name__)


def create_smtp_ssl_context(*, verify_ssl: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not verify_ssl:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    # Avoid hanging forever on flaky shared-hosting SSL (Namecheap etc.)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def _open_smtp_connection(
    *,
    smtp_server: SmtpServer,
    timeout: int,
    verify_ssl: bool,
    host: str | None = None,
    port: int | None = None,
    encryption: str | None = None,
) -> smtplib.SMTP:
    password = decrypt_value(smtp_server.password_encrypted)
    context = create_smtp_ssl_context(verify_ssl=verify_ssl)
    host = host or smtp_server.host
    port = port if port is not None else smtp_server.port
    encryption = encryption or smtp_server.encryption

    if encryption == SmtpServer.Encryption.SSL:
        server = smtplib.SMTP_SSL(
            host,
            port,
            timeout=timeout,
            context=context,
        )
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        if encryption == SmtpServer.Encryption.TLS:
            server.starttls(context=context)

    if smtp_server.username:
        server.login(smtp_server.username, password)

    return server


def _is_handshake_timeout(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        isinstance(exc, TimeoutError)
        or "handshake operation timed out" in message
        or "timed out" in message
    )


def connect_smtp_server(*, smtp_server: SmtpServer, timeout: int = 60) -> smtplib.SMTP:
    """Connect with retries; Namecheap SSL on 465 can flake with handshake timeouts."""
    verify_ssl = smtp_server.verify_ssl
    last_error: BaseException | None = None

    for attempt in range(1, 4):
        try:
            return _open_smtp_connection(
                smtp_server=smtp_server,
                timeout=timeout,
                verify_ssl=verify_ssl,
            )
        except ssl.SSLCertVerificationError as exc:
            last_error = exc
            if verify_ssl:
                logger.warning(
                    "SSL certificate mismatch for %s — disabling verify_ssl for shared hosting.",
                    smtp_server.host,
                )
                verify_ssl = False
                smtp_server.verify_ssl = False
                smtp_server.save(update_fields=["verify_ssl", "updated_at"])
                continue
            raise
        except (TimeoutError, OSError, ssl.SSLError, smtplib.SMTPServerDisconnected) as exc:
            last_error = exc
            if not _is_handshake_timeout(exc) and not isinstance(exc, TimeoutError):
                # Non-timeout connection errors: still retry once, then try 587.
                if attempt >= 2:
                    break
            logger.warning(
                "SMTP connect attempt %s/%s to %s:%s failed: %s",
                attempt,
                3,
                smtp_server.host,
                smtp_server.port,
                exc,
            )
            time.sleep(min(2 * attempt, 5))

    # Fallback: many cPanel hosts accept STARTTLS on 587 when 465 SSL hangs.
    if (
        smtp_server.encryption == SmtpServer.Encryption.SSL
        and int(smtp_server.port) == 465
    ):
        logger.warning(
            "SMTP SSL :465 handshake failed for %s — trying STARTTLS :587",
            smtp_server.host,
        )
        try:
            return _open_smtp_connection(
                smtp_server=smtp_server,
                timeout=timeout,
                verify_ssl=False,
                port=587,
                encryption=SmtpServer.Encryption.TLS,
            )
        except Exception as exc:
            last_error = exc
            logger.warning("SMTP STARTTLS :587 fallback failed: %s", exc)

    if last_error:
        raise last_error
    raise smtplib.SMTPException(f"Could not connect to {smtp_server.host}:{smtp_server.port}")
