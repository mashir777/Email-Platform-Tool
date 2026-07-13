from django.urls import path

from tracking.views import ClickTrackingRedirectView, OpenTrackingPixelView, ViewEmailTrackingView

app_name = "tracking"

urlpatterns = [
    path("open/<path:token>", OpenTrackingPixelView.as_view(), name="open-pixel"),
    path("view/<path:token>/", ViewEmailTrackingView.as_view(), name="view-email"),
    path("click/<path:token>/", ClickTrackingRedirectView.as_view(), name="click-redirect"),
]
