from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import success_response
from reports import services
from reports.serializers import CampaignReportSerializer, ReportOverviewSerializer


class ReportOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reports"], summary="Get reporting overview")
    def get(self, request):
        stats = services.get_overview_stats(request.user)
        return success_response(data={"overview": ReportOverviewSerializer(stats).data})


class CampaignReportListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reports"], summary="Get per-campaign performance reports")
    def get(self, request):
        search = request.query_params.get("search")
        status_filter = request.query_params.get("status")
        reports = services.get_campaign_reports(
            request.user,
            search=search,
            status=status_filter,
        )
        return success_response(
            data={"reports": CampaignReportSerializer(reports, many=True).data},
        )
