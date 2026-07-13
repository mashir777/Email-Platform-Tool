from django.urls import path

from reports.views import CampaignReportListView, ReportOverviewView

app_name = "reports"

urlpatterns = [
    path("overview/", ReportOverviewView.as_view(), name="overview"),
    path("campaigns/", CampaignReportListView.as_view(), name="campaigns"),
]
