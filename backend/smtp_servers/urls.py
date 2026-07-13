from django.urls import path

from smtp_servers.views import (
    SmtpServerCollectionView,
    SmtpServerDetailView,
    SmtpServerImportView,
    SmtpServerSetDefaultView,
    SmtpServerTestView,
    SmtpStatsView,
)

app_name = "smtp"

urlpatterns = [
    path("stats/", SmtpStatsView.as_view(), name="stats"),
    path("import/", SmtpServerImportView.as_view(), name="import"),
    path("", SmtpServerCollectionView.as_view(), name="server-list"),
    path("<uuid:server_id>/", SmtpServerDetailView.as_view(), name="server-detail"),
    path("<uuid:server_id>/default/", SmtpServerSetDefaultView.as_view(), name="set-default"),
    path("<uuid:server_id>/test/", SmtpServerTestView.as_view(), name="test"),
]
