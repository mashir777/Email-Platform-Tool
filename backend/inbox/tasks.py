from celery import shared_task


@shared_task(name="inbox.tasks.sync_all_inboxes")
def sync_all_inboxes():
    from accounts.models import User
    from inbox.services import sync_owner_inboxes

    total = 0
    for user in User.objects.filter(is_active=True, is_verified=True):
        if not user.smtp_servers.filter(is_active=True).exists():
            continue
        result = sync_owner_inboxes(owner=user)
        total += result.get("new_messages", 0)
    return {"new_messages": total}
