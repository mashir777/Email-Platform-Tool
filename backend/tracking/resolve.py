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
