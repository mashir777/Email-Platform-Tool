from django.urls import path

from reports.views import (
    CampaignReportListView,
    DailySendOpenDetailView,
    DailySendOpenReportView,
    ReportOverviewView,
)

app_name = "reports"

urlpatterns = [
    path("overview/", ReportOverviewView.as_view(), name="overview"),
    path("campaigns/", CampaignReportListView.as_view(), name="campaigns"),
    path("daily/", DailySendOpenReportView.as_view(), name="daily"),
    path("daily/<str:day>/", DailySendOpenDetailView.as_view(), name="daily-detail"),
]
