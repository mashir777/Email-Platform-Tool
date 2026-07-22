from celery import shared_task
from django.utils import timezone


@shared_task(name="smtp_servers.tasks.advance_warmup_limits")
def advance_warmup_limits():
    """Bump warmup_current_daily toward target for enabled SMTP senders."""
    from smtp_servers.models import SmtpServer

    updated = 0
    for server in SmtpServer.objects.filter(warmup_enabled=True, is_active=True):
        start = max(int(server.warmup_start_daily or 1), 1)
        target = max(int(server.warmup_target_daily or start), start)
        increase = max(int(server.warmup_increase_daily or 1), 1)
        current = int(server.warmup_current_daily or 0)
        if current <= 0:
            current = start
        if current >= target:
            continue
        server.warmup_current_daily = min(target, current + increase)
        if not server.warmup_started_at:
            server.warmup_started_at = timezone.now()
        server.save(update_fields=["warmup_current_daily", "warmup_started_at", "updated_at"])
        updated += 1
    return {"updated": updated}
