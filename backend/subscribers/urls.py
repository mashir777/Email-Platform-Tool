from django.urls import path

from subscribers.views import (
    SubscriberBulkDeleteView,
    SubscriberDetailView,
    SubscriberImportView,
    SubscriberCollectionView,
    SubscriberListDetailView,
    SubscriberListListCreateView,
    SubscriberStatsView,
)

app_name = "subscribers"

urlpatterns = [
    path("stats/", SubscriberStatsView.as_view(), name="stats"),
    path("lists/", SubscriberListListCreateView.as_view(), name="list-list"),
    path("lists/<uuid:list_id>/", SubscriberListDetailView.as_view(), name="list-detail"),
    path("", SubscriberCollectionView.as_view(), name="subscriber-list"),
    path("import/", SubscriberImportView.as_view(), name="import"),
    path("bulk-delete/", SubscriberBulkDeleteView.as_view(), name="bulk-delete"),
    path("<uuid:subscriber_id>/", SubscriberDetailView.as_view(), name="subscriber-detail"),
]
