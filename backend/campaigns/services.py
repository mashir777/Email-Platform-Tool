from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from campaigns.models import Campaign
from email_templates.models import MessageVersion
from sending.services import get_active_smtp_servers, get_default_smtp_server
from subscribers.models import Subscriber, SubscriberList


def get_owner_campaigns(user):
    return Campaign.objects.filter(owner=user).select_related(
        "subscriber_list",
        "message_version",
        "message_version__purpose",
    )


def get_owner_campaign(user, campaign_id):
    return Campaign.objects.select_related(
        "subscriber_list",
        "message_version",
        "message_version__purpose",
    ).get(
        id=campaign_id,
        owner=user,
    )


def _normalize_smtp_server_ids(owner, raw_ids):
    """Keep only active SMTP IDs owned by this user; store as strings."""
    if raw_ids is None:
        return None
    if not raw_ids:
        return []
    allowed = {str(s.id) for s in get_active_smtp_servers(owner)}
    normalized = []
    for value in raw_ids:
        sid = str(value)
        if sid in allowed and sid not in normalized:
            normalized.append(sid)
    if not normalized:
        raise ValidationError(
            {"smtp_server_ids": ["Select at least one active sender."]},
        )
    return normalized


def _validate_list_owner(subscriber_list, owner):
    if subscriber_list.owner_id != owner.id:
        raise ValidationError({"subscriber_list_id": ["Invalid subscriber list."]})
    if not subscriber_list.is_active:
        raise ValidationError({"subscriber_list_id": ["Subscriber list is inactive."]})


def resolve_message_version(owner, version_id):
    if not version_id:
        return None
    try:
        return MessageVersion.objects.select_related("purpose").get(
            id=version_id,
            purpose__owner=owner,
        )
    except MessageVersion.DoesNotExist as exc:
        raise ValidationError(
            {"message_version_id": ["Invalid message version."]},
        ) from exc


def _count_recipients(subscriber_list):
    return subscriber_list.subscribers.filter(
        status=Subscriber.Status.SUBSCRIBED,
    ).count()


def _validate_from_email_for_owner(*, owner, from_email: str):
    if not from_email:
        return
    smtp_server = get_default_smtp_server(owner)
    if not smtp_server or not smtp_server.from_email:
        return
    allowed_domain = smtp_server.from_email.rsplit("@", 1)[-1].lower()
    from_domain = from_email.rsplit("@", 1)[-1].lower()
    if from_domain != allowed_domain:
        raise ValidationError(
            {
                "from_email": [
                    f"Use an address on your sending domain (@{allowed_domain}), "
                    f"not @{from_domain}. Your SMTP server blocks other domains.",
                ],
            },
        )


def _default_from_fields(owner):
    smtp_server = get_default_smtp_server(owner)
    if not smtp_server:
        return "", ""
    return smtp_server.from_name or "", smtp_server.from_email or ""


@transaction.atomic
def create_campaign(*, owner, name, **fields):
    if Campaign.objects.filter(owner=owner, name=name).exists():
        raise ValidationError({"name": ["A campaign with this name already exists."]})

    subscriber_list = fields.get("subscriber_list")
    if subscriber_list:
        _validate_list_owner(subscriber_list, owner)

    default_name, default_email = _default_from_fields(owner)
    if not fields.get("from_email"):
        fields["from_email"] = default_email
    if not fields.get("from_name"):
        fields["from_name"] = default_name

    if fields.get("from_email"):
        _validate_from_email_for_owner(owner=owner, from_email=fields["from_email"])

    if "smtp_server_ids" in fields:
        fields["smtp_server_ids"] = _normalize_smtp_server_ids(
            owner,
            fields.get("smtp_server_ids"),
        )

    return Campaign.objects.create(owner=owner, name=name, **fields)


@transaction.atomic
def update_campaign(*, campaign, **validated_data):
    if campaign.status not in {Campaign.Status.DRAFT, Campaign.Status.SCHEDULED}:
        raise ValidationError(
            {"status": ["Only draft or scheduled campaigns can be edited."]},
        )

    new_name = validated_data.get("name")
    if (
        new_name
        and new_name != campaign.name
        and Campaign.objects.filter(owner=campaign.owner, name=new_name)
        .exclude(pk=campaign.pk)
        .exists()
    ):
        raise ValidationError({"name": ["A campaign with this name already exists."]})

    subscriber_list = validated_data.get("subscriber_list")
    if subscriber_list:
        _validate_list_owner(subscriber_list, campaign.owner)

    if validated_data.get("from_email"):
        _validate_from_email_for_owner(
            owner=campaign.owner,
            from_email=validated_data["from_email"],
        )

    if "smtp_server_ids" in validated_data:
        validated_data["smtp_server_ids"] = _normalize_smtp_server_ids(
            campaign.owner,
            validated_data.get("smtp_server_ids"),
        )

    for field, value in validated_data.items():
        setattr(campaign, field, value)
    campaign.save()
    return campaign


@transaction.atomic
def delete_campaign(*, campaign):
    if campaign.status == Campaign.Status.SENDING:
        raise ValidationError({"status": ["Cannot delete a campaign that is sending."]})
    campaign.delete()


@transaction.atomic
def schedule_campaign(*, campaign, scheduled_at):
    if campaign.status != Campaign.Status.DRAFT:
        raise ValidationError({"status": ["Only draft campaigns can be scheduled."]})

    if not campaign.subscriber_list_id:
        raise ValidationError({"subscriber_list_id": ["A subscriber list is required."]})

    if not campaign.subject:
        raise ValidationError({"subject": ["Subject is required to schedule."]})

    if not campaign.html_content and not campaign.text_content:
        raise ValidationError(
            {"html_content": ["Email content is required to schedule."]},
        )

    if scheduled_at <= timezone.now():
        raise ValidationError({"scheduled_at": ["Scheduled time must be in the future."]})

    recipient_count = _count_recipients(campaign.subscriber_list)
    if recipient_count == 0:
        raise ValidationError(
            {"subscriber_list_id": ["Subscriber list has no active subscribers."]},
        )

    campaign.status = Campaign.Status.SCHEDULED
    campaign.scheduled_at = scheduled_at
    campaign.recipient_count = recipient_count
    campaign.save()

    from django.conf import settings

    if not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        from sending.tasks import dispatch_campaign

        dispatch_campaign.apply_async(args=[str(campaign.id)], eta=scheduled_at)

    return campaign


def send_campaign_now(*, campaign):
    from django.conf import settings

    from sending.tasks import dispatch_campaign

    # Queue + dispatch (eager in local development; async in production)
    dispatch_campaign.delay(str(campaign.id))
    campaign.refresh_from_db()

    # In eager mode the campaign should already be sent; refresh status for response
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        campaign.refresh_from_db()
    return campaign


@transaction.atomic
def cancel_campaign(*, campaign):
    if campaign.status not in {Campaign.Status.SCHEDULED, Campaign.Status.PAUSED}:
        raise ValidationError(
            {"status": ["Only scheduled or paused campaigns can be cancelled."]},
        )

    campaign.status = Campaign.Status.CANCELLED
    campaign.scheduled_at = None
    campaign.save()
    return campaign


@transaction.atomic
def pause_campaign(*, campaign):
    """Stop an in-progress send. Pending queue items stay until Resume Send."""
    if campaign.status == Campaign.Status.PAUSED:
        return campaign

    if campaign.status != Campaign.Status.SENDING:
        raise ValidationError(
            {"status": ["Only sending campaigns can be stopped."]},
        )

    # Cancel any already-scheduled Timer / countdown so sending actually stops.
    from sending.queue_control import bump_queue_run_generation

    bump_queue_run_generation()

    campaign.status = Campaign.Status.PAUSED
    campaign.save(update_fields=["status", "updated_at"])
    return campaign


@transaction.atomic
def duplicate_campaign(*, campaign):
    base_name = f"{campaign.name} (Copy)"
    name = base_name
    counter = 1
    while Campaign.objects.filter(owner=campaign.owner, name=name).exists():
        counter += 1
        name = f"{base_name} {counter}"

    default_name, default_email = _default_from_fields(campaign.owner)

    return Campaign.objects.create(
        owner=campaign.owner,
        name=name,
        subject=campaign.subject,
        from_name=campaign.from_name or default_name,
        from_email=default_email or campaign.from_email,
        html_content=campaign.html_content,
        text_content=campaign.text_content,
        subscriber_list=campaign.subscriber_list,
        status=Campaign.Status.DRAFT,
    )


def resolve_subscriber_list(owner, list_id):
    if not list_id:
        return None
    try:
        return SubscriberList.objects.get(id=list_id, owner=owner)
    except SubscriberList.DoesNotExist as exc:
        raise ValidationError({"subscriber_list_id": ["Subscriber list not found."]}) from exc
