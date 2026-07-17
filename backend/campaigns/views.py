from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from campaigns import services
from campaigns.models import Campaign
from campaigns.permissions import CanManageCampaigns, IsCampaignOwner
from campaigns.serializers import (
    CampaignCreateSerializer,
    CampaignScheduleSerializer,
    CampaignSerializer,
    CampaignStatsSerializer,
    CampaignUpdateSerializer,
)
from core.responses import error_response, success_response


class CampaignStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Campaigns"], summary="Get campaign statistics")
    def get(self, request):
        qs = services.get_owner_campaigns(request.user)
        stats = {
            "total": qs.count(),
            "draft": qs.filter(status=Campaign.Status.DRAFT).count(),
            "scheduled": qs.filter(status=Campaign.Status.SCHEDULED).count(),
            "sent": qs.filter(status=Campaign.Status.SENT).count(),
            "cancelled": qs.filter(status=Campaign.Status.CANCELLED).count(),
        }
        return success_response(data={"stats": CampaignStatsSerializer(stats).data})


class CampaignCollectionView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns]

    @extend_schema(tags=["Campaigns"], summary="List campaigns")
    def get(self, request):
        qs = services.get_owner_campaigns(request.user)
        status_filter = request.query_params.get("status")
        search = request.query_params.get("search")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(subject__icontains=search)
        return success_response(
            data={"campaigns": CampaignSerializer(qs, many=True).data},
        )

    @extend_schema(
        tags=["Campaigns"],
        request=CampaignCreateSerializer,
        summary="Create a campaign",
    )
    def post(self, request):
        serializer = CampaignCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        list_id = data.pop("subscriber_list_id", None)
        message_version_id = data.pop("message_version_id", None)

        try:
            subscriber_list = services.resolve_subscriber_list(request.user, list_id)
            message_version = services.resolve_message_version(
                request.user,
                message_version_id,
            )
            campaign = services.create_campaign(
                owner=request.user,
                subscriber_list=subscriber_list,
                message_version=message_version,
                **data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"campaign": CampaignSerializer(campaign).data},
            message="Campaign created successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class CampaignDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    def get_object(self, request, campaign_id):
        campaign = get_object_or_404(
            Campaign.objects.select_related(
                "subscriber_list",
                "message_version",
                "message_version__purpose",
            ),
            id=campaign_id,
            owner=request.user,
        )
        self.check_object_permissions(request, campaign)
        return campaign

    @extend_schema(tags=["Campaigns"], summary="Get campaign details")
    def get(self, request, campaign_id):
        campaign = self.get_object(request, campaign_id)
        return success_response(data={"campaign": CampaignSerializer(campaign).data})

    @extend_schema(
        tags=["Campaigns"],
        request=CampaignUpdateSerializer,
        summary="Update campaign",
    )
    def patch(self, request, campaign_id):
        campaign = self.get_object(request, campaign_id)
        serializer = CampaignUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        if "subscriber_list_id" in data:
            list_id = data.pop("subscriber_list_id")
            data["subscriber_list"] = services.resolve_subscriber_list(
                request.user,
                list_id,
            )
        if "message_version_id" in data:
            message_version_id = data.pop("message_version_id")
            data["message_version"] = services.resolve_message_version(
                request.user,
                message_version_id,
            )

        try:
            campaign = services.update_campaign(campaign=campaign, **data)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"campaign": CampaignSerializer(campaign).data},
            message="Campaign updated successfully.",
        )

    @extend_schema(tags=["Campaigns"], summary="Delete campaign")
    def delete(self, request, campaign_id):
        campaign = self.get_object(request, campaign_id)
        try:
            services.delete_campaign(campaign=campaign)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)
        return success_response(message="Campaign deleted successfully.")


class CampaignScheduleView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(
        tags=["Campaigns"],
        request=CampaignScheduleSerializer,
        summary="Schedule a draft campaign",
    )
    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, owner=request.user)
        self.check_object_permissions(request, campaign)

        serializer = CampaignScheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            campaign = services.schedule_campaign(
                campaign=campaign,
                scheduled_at=serializer.validated_data["scheduled_at"],
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"campaign": CampaignSerializer(campaign).data},
            message="Campaign scheduled successfully.",
        )


class CampaignCancelView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(tags=["Campaigns"], summary="Cancel a scheduled campaign")
    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, owner=request.user)
        self.check_object_permissions(request, campaign)

        try:
            campaign = services.cancel_campaign(campaign=campaign)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"campaign": CampaignSerializer(campaign).data},
            message="Campaign cancelled successfully.",
        )


class CampaignPauseView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(tags=["Campaigns"], summary="Stop an in-progress campaign send")
    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, owner=request.user)
        self.check_object_permissions(request, campaign)

        try:
            campaign = services.pause_campaign(campaign=campaign)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"campaign": CampaignSerializer(campaign).data},
            message="Sending stopped.",
        )


class CampaignDuplicateView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(tags=["Campaigns"], summary="Duplicate a campaign")
    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, owner=request.user)
        self.check_object_permissions(request, campaign)

        duplicate = services.duplicate_campaign(campaign=campaign)
        return success_response(
            data={"campaign": CampaignSerializer(duplicate).data},
            message="Campaign duplicated successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class CampaignSendView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(tags=["Campaigns"], summary="Send a campaign now")
    def post(self, request, campaign_id):
        campaign = get_object_or_404(
            Campaign.objects.select_related("subscriber_list"),
            id=campaign_id,
            owner=request.user,
        )
        self.check_object_permissions(request, campaign)

        from tracking.context import set_campaign_tracking_base_url, set_tracking_base_url
        from tracking.resolve import resolve_tracking_base_url

        tracking_base = resolve_tracking_base_url(
            request=request,
            header_value=request.headers.get("X-Tracking-Base-Url", ""),
        )
        set_tracking_base_url(tracking_base)
        set_campaign_tracking_base_url(str(campaign.id), tracking_base)
        try:
            campaign = services.send_campaign_now(campaign=campaign)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)
        finally:
            set_tracking_base_url(None)

        from sending.services import get_campaign_send_summary

        summary = get_campaign_send_summary(campaign)
        sent = summary["sent"]
        failed = summary["failed"]
        pending = summary["pending"]
        skipped = summary.get("skipped", 0)
        interval = summary.get("send_interval_seconds", 60)
        if pending and campaign.status == Campaign.Status.SENDING:
            minutes = max(1, interval // 60)
            message = (
                f"Campaign send started. {sent} sent, {pending} queued. "
                f"Sending ~1 email every {minutes} minute(s) based on your SMTP limits."
            )
        elif failed:
            first_error = summary["errors"][0]["error"] if summary.get("errors") else ""
            message = f"Delivered: {sent}, Failed: {failed}."
            if skipped:
                message += f" Skipped: {skipped} (fake @example.com addresses)."
            if first_error:
                message += f" Error: {first_error[:200]}"
        elif sent and skipped:
            message = (
                f"Delivered: {sent} real email(s). "
                f"Skipped: {skipped} fake/test addresses (@example.com cannot receive mail)."
            )
        elif sent:
            message = f"Campaign sent successfully to {sent} recipient(s)."
        elif skipped:
            message = (
                f"No emails delivered. {skipped} address(es) skipped — "
                "add a real Gmail in the recipient field below."
            )
        else:
            message = "Campaign send started."

        return success_response(
            data={
                "campaign": CampaignSerializer(campaign).data,
                "send_summary": summary,
            },
            message=message,
        )


class CampaignTestSendView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(tags=["Campaigns"], summary="Send a one-off test email for this campaign")
    def post(self, request, campaign_id):
        from campaigns.serializers import CampaignTestSendSerializer
        from sending.services import send_campaign_test_email

        campaign = get_object_or_404(
            Campaign.objects.select_related("subscriber_list"),
            id=campaign_id,
            owner=request.user,
        )
        self.check_object_permissions(request, campaign)

        serializer = CampaignTestSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = send_campaign_test_email(
                campaign=campaign,
                to_email=serializer.validated_data["to_email"],
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data=result,
            message=f"Test email sent to {result['to_email']}. Check inbox and spam folder.",
        )


class CampaignDeliveryStatusView(APIView):
    permission_classes = [IsAuthenticated, CanManageCampaigns, IsCampaignOwner]

    @extend_schema(tags=["Campaigns"], summary="Per-recipient delivery and open tracking")
    def get(self, request, campaign_id):
        from sending.services import get_campaign_send_summary
        from tracking.services import get_campaign_delivery_tracking

        campaign = get_object_or_404(Campaign, id=campaign_id, owner=request.user)
        self.check_object_permissions(request, campaign)

        return success_response(
            data={
                "tracking": get_campaign_delivery_tracking(campaign=campaign),
                "send_summary": get_campaign_send_summary(campaign),
            },
        )
