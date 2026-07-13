import csv
import io

from django.core.exceptions import ValidationError
from django.db import transaction

from smtp_servers.models import SmtpServer


REQUIRED_COLUMNS = {"name", "host", "port", "username", "password", "from_email"}
OPTIONAL_COLUMNS = {
    "from_name",
    "encryption",
    "hourly_limit",
    "daily_limit",
    "verify_ssl",
    "is_active",
    "is_default",
}


def import_smtp_servers_from_csv(*, owner, csv_file):
    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValidationError({"file": ["CSV file is empty or has no header row."]})

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise ValidationError(
            {
                "file": [
                    f"CSV must include columns: {', '.join(sorted(REQUIRED_COLUMNS))}. "
                    f"Missing: {', '.join(sorted(missing))}.",
                ],
            },
        )

    created = 0
    updated = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        name = normalized.get("name", "")
        from_email = normalized.get("from_email", "").lower()

        if not name or not from_email:
            skipped += 1
            continue

        try:
            port = int(normalized.get("port") or "587")
            hourly_limit = int(normalized.get("hourly_limit") or "60")
            daily_limit = int(normalized.get("daily_limit") or "1000")
            encryption = (normalized.get("encryption") or "tls").lower()
            if encryption not in {c.value for c in SmtpServer.Encryption}:
                raise ValueError(f"Invalid encryption '{encryption}'")

            verify_ssl_raw = (normalized.get("verify_ssl") or "false").lower()
            verify_ssl = verify_ssl_raw in {"1", "true", "yes"}
            is_active_raw = (normalized.get("is_active") or "true").lower()
            is_active = is_active_raw in {"1", "true", "yes"}
            is_default_raw = (normalized.get("is_default") or "false").lower()
            is_default = is_default_raw in {"1", "true", "yes"}

            fields = {
                "name": name,
                "host": normalized.get("host", ""),
                "port": port,
                "username": normalized.get("username", ""),
                "encryption": encryption,
                "from_email": from_email,
                "from_name": normalized.get("from_name", ""),
                "hourly_limit": hourly_limit,
                "daily_limit": daily_limit,
                "verify_ssl": verify_ssl,
                "is_active": is_active,
                "is_default": is_default,
            }
            password = normalized.get("password", "")

            existing = SmtpServer.objects.filter(owner=owner, from_email=from_email).first()
            if existing:
                from smtp_servers.services import update_smtp_server

                update_smtp_server(
                    smtp_server=existing,
                    password=password or None,
                    **fields,
                )
                updated += 1
            else:
                from smtp_servers.services import create_smtp_server

                create_smtp_server(owner=owner, password=password, **fields)
                created += 1
        except Exception as exc:
            errors.append(f"Row {row_num} ({name or from_email}): {exc}")
            skipped += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
    }
