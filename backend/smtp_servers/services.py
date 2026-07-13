import smtplib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.encryption import encrypt_value
from smtp_servers.connection import connect_smtp_server
from smtp_servers.models import SmtpServer


def get_owner_smtp_servers(user):
    return SmtpServer.objects.filter(owner=user)


def get_owner_smtp_server(user, server_id):
    return SmtpServer.objects.get(id=server_id, owner=user)


def _clear_default_flag(owner, exclude_id=None):
    qs = SmtpServer.objects.filter(owner=owner, is_default=True)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    qs.update(is_default=False)


@transaction.atomic
def create_smtp_server(*, owner, password, **fields):
    name = fields.get("name")
    if SmtpServer.objects.filter(owner=owner, name=name).exists():
        raise ValidationError({"name": ["An SMTP server with this name already exists."]})

    if fields.get("is_default"):
        _clear_default_flag(owner)

    encrypted = encrypt_value(password) if password else ""
    return SmtpServer.objects.create(
        owner=owner,
        password_encrypted=encrypted,
        **fields,
    )


@transaction.atomic
def update_smtp_server(*, smtp_server, password=None, **validated_data):
    new_name = validated_data.get("name")
    if (
        new_name
        and new_name != smtp_server.name
        and SmtpServer.objects.filter(owner=smtp_server.owner, name=new_name)
        .exclude(pk=smtp_server.pk)
        .exists()
    ):
        raise ValidationError({"name": ["An SMTP server with this name already exists."]})

    if validated_data.get("is_default"):
        _clear_default_flag(smtp_server.owner, exclude_id=smtp_server.id)

    if password:
        validated_data["password_encrypted"] = encrypt_value(password)

    for field, value in validated_data.items():
        setattr(smtp_server, field, value)
    smtp_server.save()
    return smtp_server


@transaction.atomic
def delete_smtp_server(*, smtp_server):
    smtp_server.delete()


@transaction.atomic
def set_default_smtp_server(*, smtp_server):
    if not smtp_server.is_active:
        raise ValidationError({"is_active": ["Inactive server cannot be set as default."]})
    _clear_default_flag(smtp_server.owner, exclude_id=smtp_server.id)
    smtp_server.is_default = True
    smtp_server.save()
    return smtp_server


def test_smtp_connection(*, smtp_server):
    message = ""
    success = False

    try:
        with connect_smtp_server(smtp_server=smtp_server, timeout=15):
            success = True
            message = "Connection successful."
    except smtplib.SMTPException as exc:
        message = str(exc)
    except OSError as exc:
        message = str(exc)
    except Exception as exc:
        message = str(exc)

    smtp_server.last_tested_at = timezone.now()
    smtp_server.last_test_success = success
    smtp_server.last_test_message = message[:500]
    smtp_server.save(
        update_fields=["last_tested_at", "last_test_success", "last_test_message"],
    )
    return success, message


def get_smtp_stats(user):
    qs = get_owner_smtp_servers(user)
    return {
        "total": qs.count(),
        "active": qs.filter(is_active=True).count(),
        "inactive": qs.filter(is_active=False).count(),
        "default_configured": qs.filter(is_default=True).exists(),
    }
