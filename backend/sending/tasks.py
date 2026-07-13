from celery import shared_task


def _schedule_next_queue_run_if_pending(*, delay_seconds: int = 60):
    """Continue sending queue: 1 email, wait, next email."""
    from django.conf import settings

    from sending.services import has_pending_queue_items

    if not has_pending_queue_items():
        return

    delay = delay_seconds

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        import threading

        threading.Timer(delay, lambda: run_pending_email_queue_task()).start()
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

    from tracking.context import get_campaign_tracking_base_url, set_campaign_tracking_base_url, set_tracking_base_url
    from tracking.resolve import resolve_tracking_base_url

    tracking_base = get_campaign_tracking_base_url(str(campaign.id))
    if not tracking_base:
        tracking_base = resolve_tracking_base_url()
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
    elif campaign.status == Campaign.Status.SENDING:
        from sending.services import requeue_campaign_items

        requeued = requeue_campaign_items(campaign=campaign)
    else:
        queue_campaign(campaign=campaign)
        requeued = 0

    item_ids = get_pending_queue_item_ids(campaign.id)

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        result = run_pending_email_queue()
        campaign.refresh_from_db()
        finalize_campaign_if_complete(campaign=campaign)
        _schedule_next_queue_run_if_pending()
        return {
            "ok": True,
            "queued": len(item_ids),
            "requeued": requeued,
            "processed_now": result["processed"],
            "campaign_id": campaign_id,
        }

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
    from sending.services import (
        MIN_SEND_INTERVAL_SECONDS,
        has_pending_queue_items,
        run_pending_email_queue,
    )

    result = run_pending_email_queue()
    if has_pending_queue_items():
        _schedule_next_queue_run_if_pending(delay_seconds=MIN_SEND_INTERVAL_SECONDS)
    return result


@shared_task
def process_due_scheduled_campaigns():
    from sending.services import get_due_scheduled_campaigns

    due = list(get_due_scheduled_campaigns().values_list("id", flat=True))
    for campaign_id in due:
        dispatch_campaign.delay(str(campaign_id))
    return {"dispatched": len(due)}
