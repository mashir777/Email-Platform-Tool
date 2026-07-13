import contextvars

from django.core.cache import cache

_tracking_base_url: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tracking_base_url",
    default=None,
)

_CACHE_PREFIX = "tracking_base:"
_CACHE_TTL = 60 * 60 * 24 * 7


def set_tracking_base_url(url: str | None):
    _tracking_base_url.set(url.rstrip("/") if url else None)


def get_request_tracking_base_url() -> str | None:
    return _tracking_base_url.get()


def set_campaign_tracking_base_url(campaign_id: str, url: str):
    if url:
        cache.set(f"{_CACHE_PREFIX}{campaign_id}", url.rstrip("/"), timeout=_CACHE_TTL)


def get_campaign_tracking_base_url(campaign_id: str) -> str | None:
    return cache.get(f"{_CACHE_PREFIX}{campaign_id}")
