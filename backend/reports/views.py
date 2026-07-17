from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error_response, success_response
from reports import services
from reports.serializers import (
    CampaignReportSerializer,
    DailyReportDetailSerializer,
    DailyReportSerializer,
    ReportOverviewSerializer,
)


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


class DailySendOpenReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Reports"],
        summary="Daily sent vs opened (opens counted on send date)",
    )
    def get(self, request):
        report = services.get_daily_send_open_report(
            request.user,
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        return success_response(data={"daily": DailyReportSerializer(report).data})


class DailySendOpenDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Reports"],
        summary="Emails sent on a day with opened/waiting status",
    )
    def get(self, request, day: str):
        try:
            detail = services.get_daily_send_open_detail(request.user, day=day)
        except ValueError as exc:
            return error_response({"date": [str(exc)]})
        return success_response(
            data={"day": DailyReportDetailSerializer(detail).data},
        )
