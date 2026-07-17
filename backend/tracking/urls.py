from django.urls import path, re_path

from tracking.views import ClickTrackingRedirectView, OpenTrackingPixelView, ViewEmailTrackingView

app_name = "tracking"

urlpatterns = [
    # legacy signed-token endpoints
    path("open/<path:token>", OpenTrackingPixelView.as_view(), name="open-pixel"),
    path("view/<path:token>/", ViewEmailTrackingView.as_view(), name="view-email"),
    path("click/<path:token>/", ClickTrackingRedirectView.as_view(), name="click-redirect"),
]

try:
    from tracking.pytracking_views import PlatformClickTrackingView, PlatformOpenTrackingView

    urlpatterns = [
        re_path(
            r"^o/(?P<path>[\w=-]+)/$",
            PlatformOpenTrackingView.as_view(),
            name="pytracking-open",
        ),
        re_path(
            r"^c/(?P<path>[\w=-]+)/$",
            PlatformClickTrackingView.as_view(),
            name="pytracking-click",
        ),
        *urlpatterns,
    ]
except ImportError:
    # Server can still boot (login/API) if pytracking isn't installed in this Python.
    pass
