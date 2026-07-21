"""Lightweight send-queue control (no Celery imports)."""

# Eager-mode threading.Timer generations — bump to cancel already-scheduled sends.
_queue_run_generation = 0
_resume_delay_seconds: dict[str, int] = {}


def bump_queue_run_generation() -> int:
    """Invalidate pending Timer callbacks (Stop / before Resume)."""
    global _queue_run_generation
    _queue_run_generation += 1
    return _queue_run_generation


def current_queue_run_generation() -> int:
    return _queue_run_generation


def set_resume_delay_seconds(*, campaign_id: str, seconds: int) -> None:
    _resume_delay_seconds[str(campaign_id)] = max(0, int(seconds))


def pop_resume_delay_seconds(*, campaign_id: str) -> int | None:
    value = _resume_delay_seconds.pop(str(campaign_id), None)
    return None if value is None else max(0, int(value))
