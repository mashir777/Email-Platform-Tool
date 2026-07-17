from django.urls import include, path

app_name = "v1"

urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("subscribers/", include("subscribers.urls")),
    path("campaigns/", include("campaigns.urls")),
    path("messages/", include("email_templates.urls")),
    path("smtp/", include("smtp_servers.urls")),
    path("domains/", include("domains.urls")),
    path("reports/", include("reports.urls")),
]
