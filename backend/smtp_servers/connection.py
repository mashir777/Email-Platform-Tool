import smtplib
import ssl
import logging

from core.encryption import decrypt_value
from smtp_servers.models import SmtpServer

logger = logging.getLogger(__name__)


def create_smtp_ssl_context(*, verify_ssl: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not verify_ssl:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _open_smtp_connection(
    *,
    smtp_server: SmtpServer,
    timeout: int,
    verify_ssl: bool,
) -> smtplib.SMTP:
    password = decrypt_value(smtp_server.password_encrypted)
    context = create_smtp_ssl_context(verify_ssl=verify_ssl)

    if smtp_server.encryption == SmtpServer.Encryption.SSL:
        server = smtplib.SMTP_SSL(
            smtp_server.host,
            smtp_server.port,
            timeout=timeout,
            context=context,
        )
    else:
        server = smtplib.SMTP(smtp_server.host, smtp_server.port, timeout=timeout)
        if smtp_server.encryption == SmtpServer.Encryption.TLS:
            server.starttls(context=context)

    if smtp_server.username:
        server.login(smtp_server.username, password)

    return server


def connect_smtp_server(*, smtp_server: SmtpServer, timeout: int = 30) -> smtplib.SMTP:
    try:
        return _open_smtp_connection(
            smtp_server=smtp_server,
            timeout=timeout,
            verify_ssl=smtp_server.verify_ssl,
        )
    except ssl.SSLCertVerificationError:
        if smtp_server.verify_ssl:
            logger.warning(
                "SSL certificate mismatch for %s — disabling verify_ssl for shared hosting.",
                smtp_server.host,
            )
            smtp_server.verify_ssl = False
            smtp_server.save(update_fields=["verify_ssl", "updated_at"])
        return _open_smtp_connection(
            smtp_server=smtp_server,
            timeout=timeout,
            verify_ssl=False,
        )
