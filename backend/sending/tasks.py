from celery import shared_task

from sending.queue_control import (
    bump_queue_run_generation,
    current_queue_run_generation,
    pop_resume_delay_seconds,
)


def _schedule_next_queue_run_if_pending(*, delay_seconds: int | None = None):
    """Continue sending queue: 1 email, wait, next email."""
    from django.conf import settings
    from django.db import close_old_connections

    from sending.services import (
        MIN_SEND_INTERVAL_SECONDS,
        compute_send_interval_seconds,
        get_next_pending_queue_item,
        get_next_send_in_seconds,
        has_pending_queue_items,
    )

    if not has_pending_queue_items():
        return

    if delay_seconds is None:
        item = get_next_pending_queue_item()
        if item and item.smtp_server_id:
            remaining = get_next_send_in_seconds(smtp_server=item.smtp_server)
            if remaining > 0:
                delay_seconds = remaining
            else:
                delay_seconds = compute_send_interval_seconds(item.smtp_server)
        else:
            delay_seconds = MIN_SEND_INTERVAL_SECONDS

    delay = max(0, int(delay_seconds))
    if delay == 0:
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            run_pending_email_queue_task()
        else:
            run_pending_email_queue_task.delay()
        return

    generation = current_queue_run_generation()

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        import threading

        def _run_if_still_active():
            close_old_connections()
            try:
                if generation != current_queue_run_generation():
                    return
                run_pending_email_queue_task()
            finally:
                close_old_connections()

        threading.Timer(delay, _run_if_still_active).start()
    else:
        run_pending_email_queue_task.apply_async(countdown=delay)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_email_queue_item(self, queue_item_id: str):
    from sending.models import EmailQueueItem
    from sending.services import finalize_campaign_if_complete, process_queue_item

    try:
        queue_item = EmailQueueItem.objects.select_related(
            "campaign",
            "subscriber",
            "smtp_server",
        ).get(pk=queue_item_id)
    except EmailQueueItem.DoesNotExist:
        return {"ok": False, "reason": "not_found"}

    success = process_queue_item(queue_item=queue_item)
    finalize_campaign_if_complete(campaign=queue_item.campaign)
    return {"ok": success, "queue_item_id": queue_item_id}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def dispatch_campaign(self, campaign_id: str):
    from django.conf import settings

    from campaigns.models import Campaign
    from sending.services import (
        finalize_campaign_if_complete,
        get_pending_queue_item_ids,
        queue_campaign,
        run_pending_email_queue,
    )

    try:
        campaign = Campaign.objects.select_related("subscriber_list", "owner").get(
            pk=campaign_id,
        )
    except Campaign.DoesNotExist:
        return {"ok": False, "reason": "not_found"}

    from tracking.context import (
        get_campaign_tracking_base_url,
        set_campaign_tracking_base_url,
        set_tracking_base_url,
    )
    from tracking.resolve import resolve_tracking_base_url
    from tracking.services import is_local_tracking_url, resolve_send_tracking_base_url

    tracking_base = get_campaign_tracking_base_url(str(campaign.id))
    if not tracking_base or is_local_tracking_url(tracking_base):
        tracking_base = (
            resolve_send_tracking_base_url(
                campaign_id=str(campaign.id),
                from_email=getattr(campaign, "from_email", "") or "",
            )
            or resolve_tracking_base_url()
        )
        set_campaign_tracking_base_url(str(campaign.id), tracking_base)
    set_tracking_base_url(tracking_base)

    if campaign.status == Campaign.Status.SENT:
        from sending.services import extend_campaign_for_send

        pending_added = extend_campaign_for_send(campaign=campaign)
        if pending_added == 0:
            return {
                "ok": True,
                "reason": "no_new_recipients",
                "campaign_id": campaign_id,
            }
        requeued = 0
    elif campaign.status == Campaign.Status.PAUSED:
        # Stop → Resume: cancel old timers, then continue PENDING only (no resend).
        bump_queue_run_generation()
        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=["status", "updated_at"])
        requeued = 0
    elif campaign.status == Campaign.Status.SENDING:
        # Already sending — do not requeue/reset; just continue the pending cycle.
        bump_queue_run_generation()
        requeued = 0
    else:
        queue_campaign(campaign=campaign)
        requeued = 0

    item_ids = get_pending_queue_item_ids(campaign.id)
    resume_delay = pop_resume_delay_seconds(campaign_id=campaign_id)

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        if resume_delay is not None and resume_delay > 0:
            result = {"processed": 0}
        else:
            result = run_pending_email_queue()
        campaign.refresh_from_db()
        finalize_campaign_if_complete(campaign=campaign)
        if resume_delay is not None:
            _schedule_next_queue_run_if_pending(delay_seconds=resume_delay)
        elif result.get("processed", 0) > 0:
            from sending.services import compute_send_interval_seconds, get_next_pending_queue_item

            item = get_next_pending_queue_item()
            delay = (
                compute_send_interval_seconds(item.smtp_server)
                if item and item.smtp_server_id
                else None
            )
            _schedule_next_queue_run_if_pending(delay_seconds=delay)
        else:
            _schedule_next_queue_run_if_pending()
        return {
            "ok": True,
            "queued": len(item_ids),
            "requeued": requeued,
            "processed_now": result["processed"],
            "campaign_id": campaign_id,
        }

    if resume_delay is not None and resume_delay > 0:
        _schedule_next_queue_run_if_pending(delay_seconds=resume_delay)
    else:
        run_pending_email_queue_task.delay()
        _schedule_next_queue_run_if_pending()
    return {
        "ok": True,
        "queued": len(item_ids),
        "requeued": requeued,
        "campaign_id": campaign_id,
    }


@shared_task
def run_pending_email_queue_task():
    from django.db import close_old_connections

    from sending.services import (
        has_pending_queue_items,
        run_pending_email_queue,
    )

    close_old_connections()
    try:
        result = run_pending_email_queue()
        if has_pending_queue_items():
            if result.get("processed", 0) > 0:
                from sending.services import (
                    compute_send_interval_seconds,
                    get_next_pending_queue_item,
                )

                item = get_next_pending_queue_item()
                delay = (
                    compute_send_interval_seconds(item.smtp_server)
                    if item and item.smtp_server_id
                    else None
                )
                _schedule_next_queue_run_if_pending(delay_seconds=delay)
            else:
                _schedule_next_queue_run_if_pending()
        return result
    finally:
        close_old_connections()


@shared_task
def process_due_scheduled_campaigns():
    from sending.services import get_due_scheduled_campaigns

    due = list(get_due_scheduled_campaigns().values_list("id", flat=True))
    for campaign_id in due:
        dispatch_campaign.delay(str(campaign_id))
    return {"dispatched": len(due)}
