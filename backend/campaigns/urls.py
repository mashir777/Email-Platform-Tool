from django.urls import path

from campaigns.views import (
    CampaignCancelView,
    CampaignCollectionView,
    CampaignDeliveryStatusView,
    CampaignDetailView,
    CampaignDuplicateView,
    CampaignScheduleView,
    CampaignSendView,
    CampaignStatsView,
    CampaignTestSendView,
)

app_name = "campaigns"

urlpatterns = [
    path("stats/", CampaignStatsView.as_view(), name="stats"),
    path("", CampaignCollectionView.as_view(), name="campaign-list"),
    path("<uuid:campaign_id>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("<uuid:campaign_id>/schedule/", CampaignScheduleView.as_view(), name="schedule"),
    path("<uuid:campaign_id>/send/", CampaignSendView.as_view(), name="send"),
    path("<uuid:campaign_id>/test-send/", CampaignTestSendView.as_view(), name="test-send"),
    path("<uuid:campaign_id>/cancel/", CampaignCancelView.as_view(), name="cancel"),
    path("<uuid:campaign_id>/duplicate/", CampaignDuplicateView.as_view(), name="duplicate"),
    path(
        "<uuid:campaign_id>/delivery-status/",
        CampaignDeliveryStatusView.as_view(),
        name="delivery-status",
    ),
]
