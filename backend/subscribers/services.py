import csv
import base64
import io
import os
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from subscribers.models import ListMembership, Subscriber, SubscriberList
from subscribers.validators import is_undeliverable_email, validate_subscriber_email


def _csv_row_get(row: dict, *keys: str) -> str:
    """Read a CSV cell by exact, case-insensitive, or normalized header (First name → first_name)."""
    for key in keys:
        if key in row and row[key] is not None and str(row[key]).strip():
            return str(row[key]).strip()
    lowered = {(k or "").strip().lower(): v for k, v in row.items()}
    for key in keys:
        value = lowered.get(key.strip().lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    by_norm = {
        _normalize_merge_key(k or ""): v
        for k, v in row.items()
        if k is not None and str(k).strip()
    }
    for key in keys:
        value = by_norm.get(_normalize_merge_key(key))
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _csv_basename(csv_file) -> str:
    name = getattr(csv_file, "name", "") or ""
    return os.path.basename(name.replace("\\", "/")) or "import.csv"


def _normalize_merge_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def _csv_custom_fields(row: dict, fieldnames=None) -> dict[str, str]:
    """
    Save every CSV column so message placeholders like {{khush}} / {{First Name}} work.
    Stores both original header and normalized key → same value.
    """
    headers = list(fieldnames or row.keys())
    out: dict[str, str] = {}
    for header in headers:
        if header is None:
            continue
        raw = str(header).strip()
        if not raw:
            continue
        value = row.get(header)
        if value is None and raw in row:
            value = row.get(raw)
        text = "" if value is None else str(value).strip()
        out[raw] = text
        norm = _normalize_merge_key(raw)
        if norm:
            out[norm] = text
    return out


def _csv_header_labels(fieldnames) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for header in fieldnames or []:
        if header is None:
            continue
        raw = str(header).strip()
        if not raw:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(raw)
    return labels


def _prefer_column_label(preferred: dict[str, str], *, norm: str, label: str) -> None:
    if not norm or not label:
        return
    existing = preferred.get(norm)
    if not existing:
        preferred[norm] = label
        return
    existing_is_snake = existing == norm or not re.search(r"[A-Z\s]", existing)
    label_is_human = bool(re.search(r"[A-Z\s]", label)) and label != norm
    if existing_is_snake and label_is_human:
        preferred[norm] = label


def get_list_field_columns(subscriber_list) -> list[str]:
    """
    CSV columns to show in the emails table (everything except email / list).
    Prefers saved import headers, then samples subscriber custom_fields + model fields.
    """
    skip = {"email", "e_mail", "list"}
    preferred: dict[str, str] = {}

    headers = list(getattr(subscriber_list, "csv_headers", None) or [])
    if headers:
        for header in headers:
            norm = _normalize_merge_key(header)
            if norm in skip:
                continue
            _prefer_column_label(preferred, norm=norm, label=str(header).strip())
    else:
        sample = (
            subscriber_list.subscribers.exclude(custom_fields={})
            .values_list("custom_fields", flat=True)[:300]
        )
        for custom_fields in sample:
            for key in (custom_fields or {}):
                norm = _normalize_merge_key(key)
                if norm in skip:
                    continue
                _prefer_column_label(preferred, norm=norm, label=str(key).strip())

    qs = subscriber_list.subscribers
    if qs.exclude(first_name="").exists():
        _prefer_column_label(preferred, norm="first_name", label="First name")
    if qs.exclude(last_name="").exists():
        _prefer_column_label(preferred, norm="last_name", label="Last name")
    if qs.exclude(company="").exists():
        _prefer_column_label(preferred, norm="company", label="Company")
    if qs.exclude(industrial_company="").exists():
        _prefer_column_label(preferred, norm="industrial_company", label="Industrial Company")
    if qs.exclude(phone="").exists():
        _prefer_column_label(preferred, norm="phone", label="Phone")

    order = [
        "first_name",
        "last_name",
        "job_title",
        "jobtitle",
        "company",
        "company_name",
        "website",
        "linkedin_url",
        "linkedin",
        "phone",
        "company_url",
        "industrial_company",
        "state",
    ]
    return [
        label
        for norm, label in sorted(
            preferred.items(),
            key=lambda item: (
                order.index(item[0]) if item[0] in order else 999,
                item[1].lower(),
            ),
        )
    ]


def _store_list_csv_headers(*, list_ids: set[str], fieldnames) -> None:
    headers = _csv_header_labels(fieldnames)
    if not headers or not list_ids:
        return
    SubscriberList.objects.filter(id__in=list(list_ids)).update(csv_headers=headers)


def _list_name_from_filename(filename: str) -> str:
    stem = os.path.splitext(filename)[0].strip() or "Imported emails"
    return stem[:255]


def _subscribers_sent_since_list_import(
    *,
    owner,
    subscriber_list,
    subscriber_ids,
) -> set:
    """Subscriber IDs mailed after they were last imported into this list."""
    from sending.models import EmailQueueItem

    membership_added_at = {
        row["subscriber_id"]: row["added_at"]
        for row in ListMembership.objects.filter(
            list=subscriber_list,
            subscriber_id__in=subscriber_ids,
        ).values("subscriber_id", "added_at")
    }

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


def get_list_send_counts(*, subscriber_list, owner) -> dict:
    subscriber_ids = list(
        subscriber_list.subscribers.filter(owner=owner).values_list("id", flat=True),
    )
    total = len(subscriber_ids)
    sent = len(
        _subscribers_sent_since_list_import(
            owner=owner,
            subscriber_list=subscriber_list,
            subscriber_ids=subscriber_ids,
        ),
    )
    waiting = max(total - sent, 0)
    return {
        "total_emails": total,
        "sent_emails": sent,
        "waiting_emails": waiting,
    }


def subscriber_was_sent(*, owner, subscriber_id, subscriber_list=None) -> bool:
    from sending.models import EmailQueueItem

    if subscriber_list is None:
        return EmailQueueItem.objects.filter(
            owner=owner,
            subscriber_id=subscriber_id,
            status=EmailQueueItem.Status.SENT,
        ).exists()

    return subscriber_id in _subscribers_sent_since_list_import(
        owner=owner,
        subscriber_list=subscriber_list,
        subscriber_ids=[subscriber_id],
    )


def get_owner_lists(user):
    return SubscriberList.objects.filter(owner=user)


def get_owner_subscribers(user):
    return Subscriber.objects.filter(owner=user).prefetch_related("lists")


def delete_orphan_subscribers(*, owner) -> int:
    """Remove emails that are not on any list (keeps Total Emails accurate)."""
    import time

    from django.db.utils import OperationalError

    deleted_total = 0
    for attempt in range(1, 6):
        try:
            orphan_ids = list(
                Subscriber.objects.filter(owner=owner)
                .annotate(membership_count=Count("memberships"))
                .filter(membership_count=0)
                .values_list("id", flat=True)
            )
            if not orphan_ids:
                return deleted_total
            with transaction.atomic():
                for start in range(0, len(orphan_ids), 400):
                    chunk = orphan_ids[start : start + 400]
                    deleted_total += Subscriber.objects.filter(
                        owner=owner,
                        id__in=chunk,
                    ).delete()[0]
            return deleted_total
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= 5:
                raise
            time.sleep(0.35 * attempt)
    return deleted_total


@transaction.atomic
def create_list(*, owner, name, description="", source_filename=""):
    if SubscriberList.objects.filter(owner=owner, name=name).exists():
        raise ValidationError({"name": ["A list with this name already exists."]})
    return SubscriberList.objects.create(
        owner=owner,
        name=name,
        description=description,
        source_filename=source_filename or "",
    )


@transaction.atomic
def update_list(*, subscriber_list, **validated_data):
    new_name = validated_data.get("name")
    if (
        new_name
        and new_name != subscriber_list.name
        and SubscriberList.objects.filter(
            owner=subscriber_list.owner,
            name=new_name,
        )
        .exclude(pk=subscriber_list.pk)
        .exists()
    ):
        raise ValidationError({"name": ["A list with this name already exists."]})

    for field, value in validated_data.items():
        setattr(subscriber_list, field, value)
    subscriber_list.save()
    return subscriber_list


def delete_list(*, subscriber_list):
    """Delete list and any emails that are no longer on any list."""
    import time

    from django.db.utils import OperationalError

    owner = subscriber_list.owner
    list_id = subscriber_list.id

    for attempt in range(1, 6):
        try:
            with transaction.atomic():
                # Drop memberships first so SQLite holds a shorter write lock.
                ListMembership.objects.filter(list_id=list_id).delete()
                SubscriberList.objects.filter(id=list_id).delete()
            break
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= 5:
                raise
            time.sleep(0.35 * attempt)
    else:
        raise OperationalError("database is locked")

    delete_orphan_subscribers(owner=owner)


@transaction.atomic
def create_subscriber(*, owner, email, list_ids=None, **extra_fields):
    email = email.lower().strip()
    validate_subscriber_email(email)
    if Subscriber.objects.filter(owner=owner, email=email).exists():
        raise ValidationError({"email": ["A subscriber with this email already exists."]})

    subscriber = Subscriber.objects.create(owner=owner, email=email, **extra_fields)

    if list_ids:
        _add_subscriber_to_lists(subscriber, list_ids, owner)

    return subscriber


@transaction.atomic
def update_subscriber(*, subscriber, list_ids=None, **validated_data):
    new_email = validated_data.get("email")
    if new_email:
        new_email = new_email.lower().strip()
        if (
            new_email != subscriber.email
            and Subscriber.objects.filter(owner=subscriber.owner, email=new_email)
            .exclude(pk=subscriber.pk)
            .exists()
        ):
            raise ValidationError({"email": ["A subscriber with this email already exists."]})
        validated_data["email"] = new_email

    new_status = validated_data.get("status")
    if new_status == Subscriber.Status.UNSUBSCRIBED and subscriber.status != new_status:
        validated_data["unsubscribed_at"] = timezone.now()
    elif new_status == Subscriber.Status.SUBSCRIBED:
        validated_data["unsubscribed_at"] = None

    for field, value in validated_data.items():
        setattr(subscriber, field, value)
    subscriber.save()

    if list_ids is not None:
        subscriber.lists.clear()
        if list_ids:
            _add_subscriber_to_lists(subscriber, list_ids, subscriber.owner)

    return subscriber


@transaction.atomic
def delete_subscriber(*, subscriber):
    subscriber.delete()


@transaction.atomic
def bulk_delete_subscribers(*, owner, subscriber_ids):
    deleted, _ = Subscriber.objects.filter(
        owner=owner,
        id__in=subscriber_ids,
    ).delete()
    return deleted


def _add_subscriber_to_lists(subscriber, list_ids, owner):
    lists = SubscriberList.objects.filter(owner=owner, id__in=list_ids, is_active=True)
    found_ids = set(str(item.id) for item in lists)
    requested_ids = set(str(item) for item in list_ids)
    missing = requested_ids - found_ids
    if missing:
        raise ValidationError({"list_ids": ["One or more lists are invalid."]})

    for subscriber_list in lists:
        ListMembership.objects.get_or_create(
            list=subscriber_list,
            subscriber=subscriber,
        )


def _row_value(row: dict, *keys: str) -> str:
    normalized = {
        (key or "").strip().lower(): (value or "").strip()
        for key, value in row.items()
        if key
    }
    for key in keys:
        value = normalized.get(key.lower())
        if value:
            return value
    return ""


def _parse_list_names_from_row(row: dict) -> list[str]:
    raw = _row_value(row, "list", "lists", "list_name", "list_names")
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;|]", raw) if part.strip()]


def _get_or_create_list_by_name(*, owner, name: str, source_filename: str = ""):
    subscriber_list, created = SubscriberList.objects.get_or_create(
        owner=owner,
        name=name,
        defaults={
            "description": "",
            "source_filename": source_filename or "",
        },
    )
    if (
        not created
        and source_filename
        and subscriber_list.source_filename != source_filename
    ):
        subscriber_list.source_filename = source_filename
        subscriber_list.save(update_fields=["source_filename", "updated_at"])
    return subscriber_list, created


def _assign_subscriber_to_lists(
    *,
    subscriber,
    lists: list[SubscriberList],
    refresh_import: bool = False,
):
    seen: set[str] = set()
    for subscriber_list in lists:
        list_key = str(subscriber_list.id)
        if list_key in seen:
            continue
        seen.add(list_key)
        membership, _ = ListMembership.objects.get_or_create(
            list=subscriber_list,
            subscriber=subscriber,
        )
        if refresh_import:
            ListMembership.objects.filter(pk=membership.pk).update(
                added_at=timezone.now(),
            )


def _resolve_import_target_list(*, owner, list_id, source_filename: str, file_list_name: str):
    """Honor list_id only when it already matches this CSV's name or source_filename."""
    if not list_id:
        return None
    try:
        selected = SubscriberList.objects.get(owner=owner, id=list_id)
    except SubscriberList.DoesNotExist as exc:
        raise ValidationError({"list_id": ["List not found."]}) from exc
    if selected.name != file_list_name and selected.source_filename != source_filename:
        return None
    if source_filename and selected.source_filename != source_filename:
        selected.source_filename = source_filename
        selected.save(update_fields=["source_filename", "updated_at"])
    return selected


def _ensure_filename_list(*, owner, file_list_name: str, source_filename: str, lists_created: int):
    filename_list, created = _get_or_create_list_by_name(
        owner=owner,
        name=file_list_name,
        source_filename=source_filename,
    )
    return filename_list, lists_created + (1 if created else 0)


@transaction.atomic
def import_subscribers_from_csv(*, owner, csv_file, list_id=None):
    source_filename = _csv_basename(csv_file)
    file_list_name = _list_name_from_filename(source_filename)

    # Prefer a list matching the CSV file name so imports never mix into another list
    # (e.g. selecting "15-7-2026" while uploading "14-7-2026.csv").
    target_list = _resolve_import_target_list(
        owner=owner,
        list_id=list_id,
        source_filename=source_filename,
        file_list_name=file_list_name,
    )

    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    lowered_headers = {(name or "").strip().lower() for name in (reader.fieldnames or [])}
    if "email" not in lowered_headers:
        raise ValidationError({"file": ["CSV must include an 'email' column header."]})

    # Default destination list = CSV file name stem (created on first use)
    filename_list = target_list
    lists_created = 0
    created = 0
    updated = 0
    skipped = 0
    rejected = 0
    touched_lists: set[str] = set()

    for row in reader:
        email = _csv_row_get(row, "email").lower()
        if not email:
            skipped += 1
            continue
        if is_undeliverable_email(email):
            rejected += 1
            continue

        first_name = _csv_row_get(
            row,
            "first_name",
            "firstname",
            "First name",
            "First Name",
            "name",
        )
        last_name = _csv_row_get(
            row,
            "last_name",
            "lastname",
            "Last name",
            "Last Name",
        )
        company = _csv_row_get(
            row,
            "Company",
            "company",
            "Company Name",
            "company_name",
            "company name",
            "compny name",
            "CompanyName",
        )
        industrial_company = _csv_row_get(
            row,
            "Industrial Company",
            "industrial_company",
            "IndustrialCompany",
            "industry",
        )
        phone = _csv_row_get(
            row,
            "phone",
            "Phone",
            "Phone Number",
            "phone_number",
            "mobile",
        )[:100]
        custom_fields = _csv_custom_fields(row, reader.fieldnames)

        subscriber, was_created = Subscriber.objects.get_or_create(
            owner=owner,
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "company": company,
                "industrial_company": industrial_company,
                "custom_fields": custom_fields,
                "phone": phone,
            },
        )

        if was_created:
            created += 1
        else:
            changed = False
            for field, value in {
                "first_name": first_name,
                "last_name": last_name,
                "company": company,
                "industrial_company": industrial_company,
                "phone": phone,
            }.items():
                if value and getattr(subscriber, field) != value:
                    setattr(subscriber, field, value)
                    changed = True
            merged_custom_fields = {
                **(subscriber.custom_fields or {}),
                **custom_fields,
            }
            if subscriber.custom_fields != merged_custom_fields:
                subscriber.custom_fields = merged_custom_fields
                changed = True
            if changed:
                subscriber.save()
                updated += 1
            else:
                skipped += 1

        lists_to_assign: list[SubscriberList] = []

        # CSV "list" column still wins when present (may create additional lists)
        for list_name in _parse_list_names_from_row(row):
            subscriber_list, was_list_created = _get_or_create_list_by_name(
                owner=owner,
                name=list_name,
                source_filename=source_filename,
            )
            lists_to_assign.append(subscriber_list)
            if was_list_created:
                lists_created += 1

        if not lists_to_assign:
            if filename_list is None:
                filename_list, lists_created = _ensure_filename_list(
                    owner=owner,
                    file_list_name=file_list_name,
                    source_filename=source_filename,
                    lists_created=lists_created,
                )
            lists_to_assign.append(filename_list)

        if lists_to_assign:
            _assign_subscriber_to_lists(
                subscriber=subscriber,
                lists=lists_to_assign,
                refresh_import=True,
            )
            for item in lists_to_assign:
                touched_lists.add(str(item.id))

    primary_list = filename_list
    if primary_list is None and touched_lists:
        primary_list = SubscriberList.objects.filter(
            owner=owner,
            id__in=list(touched_lists),
        ).order_by("created_at").first()

    _store_list_csv_headers(list_ids=touched_lists, fieldnames=reader.fieldnames)

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "rejected": rejected,
        "lists_created": lists_created,
        "source_filename": source_filename,
        "lists_touched": len(touched_lists),
        "list_id": str(primary_list.id) if primary_list else None,
        "list_name": primary_list.name if primary_list else None,
    }


def filter_csv_with_reacher(*, csv_file):
    from subscribers.reacher import (
        ReacherUnavailableError,
        should_keep_email_result,
        verify_emails,
    )

    source_filename = _csv_basename(csv_file)
    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    fieldnames = reader.fieldnames or []
    lowered_headers = {(name or "").strip().lower() for name in fieldnames}
    if "email" not in lowered_headers:
        raise ValidationError({"file": ["CSV must include an 'email' column header."]})

    rows = list(reader)
    emails: list[str] = []
    for row in rows:
        email = _csv_row_get(row, "email").lower()
        if email and not is_undeliverable_email(email):
            emails.append(email)

    try:
        results = verify_emails(emails)
    except ReacherUnavailableError as exc:
        raise ValidationError({"reacher": [str(exc)]}) from exc

    kept_rows: list[dict] = []
    removed_breakdown = {
        "invalid": 0,
        "spam": 0,
        "missing_email": 0,
        "test_domain": 0,
    }

    for row in rows:
        email = _csv_row_get(row, "email").lower()
        if not email:
            removed_breakdown["missing_email"] += 1
            continue
        if is_undeliverable_email(email):
            removed_breakdown["test_domain"] += 1
            continue

        keep, reason = should_keep_email_result(results.get(email, {"is_reachable": "unknown"}))
        if keep:
            kept_rows.append(row)
            continue

        key = reason if reason in removed_breakdown else "invalid"
        removed_breakdown[key] += 1

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(kept_rows)

    stem, _ext = os.path.splitext(source_filename)
    filtered_filename = f"{stem or 'filtered'}-verified.csv"

    return {
        "source_filename": source_filename,
        "filtered_filename": filtered_filename,
        "total_rows": len(rows),
        "kept": len(kept_rows),
        "removed": len(rows) - len(kept_rows),
        "removed_breakdown": removed_breakdown,
        "filtered_csv": base64.b64encode(output.getvalue().encode("utf-8")).decode("ascii"),
    }


@transaction.atomic
def verify_list_with_reacher(*, owner, list_id):
    """Verify every email on a list and remove spam / no-inbox addresses in place."""
    from subscribers.reacher import (
        ReacherUnavailableError,
        should_keep_email_result,
        verify_emails,
    )

    try:
        subscriber_list = SubscriberList.objects.get(owner=owner, id=list_id)
    except SubscriberList.DoesNotExist as exc:
        raise ValidationError({"list_id": ["List not found."]}) from exc

    subscribers = list(subscriber_list.subscribers.filter(owner=owner))
    emails = [subscriber.email.lower().strip() for subscriber in subscribers]
    total = len(subscribers)

    try:
        results = verify_emails(emails)
    except ReacherUnavailableError as exc:
        raise ValidationError({"reacher": [str(exc)]}) from exc

    removed = 0
    removed_breakdown = {"invalid": 0, "spam": 0, "test_domain": 0}
    kept = 0

    for subscriber in subscribers:
        email = subscriber.email.lower().strip()
        if is_undeliverable_email(email):
            reason = "test_domain"
            should_keep = False
        else:
            should_keep, reason = should_keep_email_result(
                results.get(email, {"is_reachable": "unknown"}),
            )

        if should_keep:
            kept += 1
            continue

        ListMembership.objects.filter(list=subscriber_list, subscriber=subscriber).delete()
        if not subscriber.lists.exists():
            subscriber.delete()
        removed += 1
        key = reason if reason in removed_breakdown else "invalid"
        removed_breakdown[key] = removed_breakdown.get(key, 0) + 1

    subscriber_list.is_verified = True
    subscriber_list.save(update_fields=["is_verified", "updated_at"])

    return {
        "list_id": str(subscriber_list.id),
        "list_name": subscriber_list.name,
        "total": total,
        "kept": kept,
        "removed": removed,
        "removed_breakdown": removed_breakdown,
        "is_verified": True,
    }


def import_and_filter_csv_with_reacher(*, owner, csv_file, list_id=None):
    """Import a CSV, then verify with Reacher and remove spam / no-inbox emails in place."""
    # Need a fresh read for verify after import consumes the file pointer.
    if hasattr(csv_file, "seek"):
        csv_file.seek(0)
    imported = import_subscribers_from_csv(
        owner=owner,
        csv_file=csv_file,
        list_id=list_id,
    )
    target_list_id = imported.get("list_id")
    if not target_list_id:
        raise ValidationError({"file": ["Import completed but no list was created."]})

    verified = verify_list_with_reacher(owner=owner, list_id=target_list_id)
    return {
        "import": imported,
        "verify": verified,
        "list_id": verified["list_id"],
        "list_name": verified["list_name"],
        "is_verified": True,
    }
