from django.conf import settings
from pytracking import Configuration


def build_pytracking_configuration(
    *,
    campaign_id: str | None = None,
    base_url: str | None = None,
    from_email: str = "",
) -> Configuration:
    """Build pytracking Configuration using the best reachable tracking base URL."""
    from tracking.services import get_tracking_base_url, resolve_email_tracking_base_url

    if base_url:
        base = base_url.rstrip("/")
    else:
        base = resolve_email_tracking_base_url(
            campaign_id=campaign_id,
            from_email=from_email,
        ) or get_tracking_base_url(campaign_id)

    extras = dict(getattr(settings, "PYTRACKING_CONFIGURATION", {}) or {})
    extras.pop("base_open_tracking_url", None)
    extras.pop("base_click_tracking_url", None)
    extras.pop("append_slash", None)
    return Configuration(
        base_open_tracking_url=f"{base}/t/o/",
        base_click_tracking_url=f"{base}/t/c/",
        append_slash=True,
        **extras,
    )
