from django.http import HttpResponse, HttpResponseRedirect
from django.views import View

from tracking.services import TRANSPARENT_GIF_BYTES, record_open_event
from tracking.tokens import parse_open_token


class OpenTrackingPixelView(View):
    """Public 1x1 pixel — records email open when images load in Gmail/webmail."""

    def get(self, request, token: str):
        clean_token = token.removesuffix(".gif")
        try:
            queue_item_id = parse_open_token(clean_token)
            record_open_event(
                queue_item_id=queue_item_id,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            pass

        return HttpResponse(TRANSPARENT_GIF_BYTES, content_type="image/gif")


class ViewEmailTrackingView(View):
    """Link in email footer — records open and shows a simple confirmation page."""

    def get(self, request, token: str):
        try:
            queue_item_id = parse_open_token(token)
            record_open_event(
                queue_item_id=queue_item_id,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            pass

        return HttpResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
            "<p>Thank you — this email view was recorded.</p></body></html>",
            content_type="text/html",
        )


class ClickTrackingRedirectView(View):
    """Wraps links in campaign HTML — records open then redirects."""

    def get(self, request, token: str):
        target = request.GET.get("u", "")
        try:
            queue_item_id = parse_open_token(token)
            record_open_event(
                queue_item_id=queue_item_id,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            pass

        if target.startswith("http://") or target.startswith("https://"):
            return HttpResponseRedirect(target)
        return HttpResponse("Invalid link", status=400)
