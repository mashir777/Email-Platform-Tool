"""Lightweight send-queue control (no Celery imports)."""

# Eager-mode threading.Timer generations — bump to cancel already-scheduled sends.
_queue_run_generation = 0


def bump_queue_run_generation() -> int:
    """Invalidate pending Timer callbacks (Stop / before Resume)."""
    global _queue_run_generation
    _queue_run_generation += 1
    return _queue_run_generation


def current_queue_run_generation() -> int:
    return _queue_run_generation
