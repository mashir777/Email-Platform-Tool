from django.urls import path

from email_templates.views import (
    MessagePurposeCollectionView,
    MessagePurposeDetailView,
    MessageVersionDetailView,
)

app_name = "email_templates"

urlpatterns = [
    path("", MessagePurposeCollectionView.as_view(), name="purpose-list"),
    path(
        "<uuid:purpose_id>/",
        MessagePurposeDetailView.as_view(),
        name="purpose-detail",
    ),
    path(
        "versions/<uuid:version_id>/",
        MessageVersionDetailView.as_view(),
        name="version-detail",
    ),
]
