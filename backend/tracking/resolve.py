from urllib.parse import urlparse

from django.conf import settings


def _is_loopback_host(host: str) -> bool:
    if not host:
        return True
    host = host.lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_loopback_url(url: str) -> bool:
    if not url:
        return True
    return _is_loopback_host(urlparse(url).hostname or "")


def resolve_tracking_base_url(*, request=None, header_value: str = "") -> str:
    """Prefer a public tracking URL; fall back to localhost for same-PC link clicks."""
    from tracking.services import get_live_origin_backend_url, resolve_send_tracking_base_url

    header_value = (header_value or "").strip()
    resolved = resolve_send_tracking_base_url(header_value=header_value)
    if resolved:
        return resolved.rstrip("/")

    origin = get_live_origin_backend_url()
    if origin and not _is_loopback_url(origin):
        return origin.rstrip("/")

    header_value = (header_value or "").strip()
    env_url = (getattr(settings, "TRACKING_PUBLIC_BASE_URL", "") or "").strip()

    for candidate in (env_url, header_value):
        if candidate and not _is_loopback_url(candidate):
            return candidate.rstrip("/")

    if header_value:
        return header_value.rstrip("/")
    if env_url:
        return env_url.rstrip("/")
    return "http://127.0.0.1:8000"
