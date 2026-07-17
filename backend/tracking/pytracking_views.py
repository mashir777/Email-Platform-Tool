import logging

from pytracking.django import ClickTrackingView, OpenTrackingView

from tracking.services import record_open_event

logger = logging.getLogger(__name__)


def _record_from_result(tracking_result):
    metadata = tracking_result.metadata or {}
    queue_item_id = metadata.get("queue_item_id")
    if not queue_item_id:
        return
    request_data = tracking_result.request_data or {}
    record_open_event(
        queue_item_id=str(queue_item_id),
        user_agent=str(request_data.get("user_agent") or "")[:300],
        ip_address=str(request_data.get("user_ip") or "")[:64],
    )


class PlatformOpenTrackingView(OpenTrackingView):
    """Serves pytracking open pixel and records opens in our TrackingEvent table."""

    def notify_tracking_event(self, tracking_result):
        try:
            request_data = tracking_result.request_data or {}
            logger.info(
                "pytracking OPEN queue_item_id=%s ua=%s ip=%s",
                (tracking_result.metadata or {}).get("queue_item_id"),
                request_data.get("user_agent"),
                request_data.get("user_ip"),
            )
            _record_from_result(tracking_result)
        except Exception:
            logger.exception("pytracking open notify failed")

    def notify_decoding_error(self, exception, request):
        logger.warning("pytracking open decode error: %s", exception)

    def get(self, request, path):
        response = super().get(request, path)
        # Help Gmail/image proxies fetch a fresh pixel on open.
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response


class PlatformClickTrackingView(ClickTrackingView):
    """Redirects via pytracking and records open/click in TrackingEvent."""

    def notify_tracking_event(self, tracking_result):
        try:
            request_data = tracking_result.request_data or {}
            logger.info(
                "pytracking CLICK queue_item_id=%s url=%s",
                (tracking_result.metadata or {}).get("queue_item_id"),
                tracking_result.tracked_url,
            )
            _record_from_result(tracking_result)
        except Exception:
            logger.exception("pytracking click notify failed")

    def notify_decoding_error(self, exception, request):
        logger.warning("pytracking click decode error: %s", exception)
