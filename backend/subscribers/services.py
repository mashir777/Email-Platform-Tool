import csv
import io
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from subscribers.models import ListMembership, Subscriber, SubscriberList
from subscribers.validators import is_undeliverable_email, validate_subscriber_email


def get_owner_lists(user):
    return SubscriberList.objects.filter(owner=user)


def get_owner_subscribers(user):
    return Subscriber.objects.filter(owner=user).prefetch_related("lists")


@transaction.atomic
def create_list(*, owner, name, description=""):
    if SubscriberList.objects.filter(owner=owner, name=name).exists():
        raise ValidationError({"name": ["A list with this name already exists."]})
    return SubscriberList.objects.create(
        owner=owner,
        name=name,
        description=description,
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


@transaction.atomic
def delete_list(*, subscriber_list):
    subscriber_list.delete()


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


def _get_or_create_list_by_name(*, owner, name: str):
    return SubscriberList.objects.get_or_create(
        owner=owner,
        name=name,
        defaults={"description": ""},
    )


def _assign_subscriber_to_lists(*, subscriber, lists: list[SubscriberList]):
    seen: set[str] = set()
    for subscriber_list in lists:
        list_key = str(subscriber_list.id)
        if list_key in seen:
            continue
        seen.add(list_key)
        ListMembership.objects.get_or_create(
            list=subscriber_list,
            subscriber=subscriber,
        )


@transaction.atomic
def import_subscribers_from_csv(*, owner, csv_file, list_id=None):
    if list_id:
        try:
            target_list = SubscriberList.objects.get(owner=owner, id=list_id)
        except SubscriberList.DoesNotExist as exc:
            raise ValidationError({"list_id": ["List not found."]}) from exc
    else:
        target_list = None

    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or "email" not in reader.fieldnames:
        raise ValidationError({"file": ["CSV must include an 'email' column header."]})

    created = 0
    updated = 0
    skipped = 0
    rejected = 0
    lists_created = 0

    for row in reader:
        email = (row.get("email") or "").strip().lower()
        if not email:
            skipped += 1
            continue
        if is_undeliverable_email(email):
            rejected += 1
            continue

        first_name = (row.get("first_name") or row.get("firstname") or "").strip()
        last_name = (row.get("last_name") or row.get("lastname") or "").strip()
        phone = (row.get("phone") or "").strip()

        subscriber, was_created = Subscriber.objects.get_or_create(
            owner=owner,
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
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
                "phone": phone,
            }.items():
                if value and getattr(subscriber, field) != value:
                    setattr(subscriber, field, value)
                    changed = True
            if changed:
                subscriber.save()
                updated += 1
            else:
                skipped += 1

        lists_to_assign: list[SubscriberList] = []
        if target_list:
            lists_to_assign.append(target_list)

        for list_name in _parse_list_names_from_row(row):
            subscriber_list, was_list_created = _get_or_create_list_by_name(
                owner=owner,
                name=list_name,
            )
            lists_to_assign.append(subscriber_list)
            if was_list_created:
                lists_created += 1

        if lists_to_assign:
            _assign_subscriber_to_lists(subscriber=subscriber, lists=lists_to_assign)

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "rejected": rejected,
        "lists_created": lists_created,
    }
