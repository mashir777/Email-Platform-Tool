from django.urls import path

from domains.views import (
    DomainCollectionView,
    DomainDetailView,
    DomainSetDefaultView,
    DomainStatsView,
    DomainVerifyView,
)

app_name = "domains"

urlpatterns = [
    path("stats/", DomainStatsView.as_view(), name="stats"),
    path("", DomainCollectionView.as_view(), name="domain-list"),
    path("<uuid:domain_id>/", DomainDetailView.as_view(), name="domain-detail"),
    path("<uuid:domain_id>/default/", DomainSetDefaultView.as_view(), name="set-default"),
    path("<uuid:domain_id>/verify/", DomainVerifyView.as_view(), name="verify"),
]
