from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error_response, success_response
from domains import services
from domains.models import SendingDomain
from domains.permissions import CanManageDomains, IsDomainOwner
from domains.serializers import (
    DomainStatsSerializer,
    SendingDomainCreateSerializer,
    SendingDomainSerializer,
    SendingDomainUpdateSerializer,
)


class DomainStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Domains"], summary="Get domain statistics")
    def get(self, request):
        stats = services.get_domain_stats(request.user)
        return success_response(data={"stats": DomainStatsSerializer(stats).data})


class DomainCollectionView(APIView):
    permission_classes = [IsAuthenticated, CanManageDomains]

    @extend_schema(tags=["Domains"], summary="List sending domains")
    def get(self, request):
        qs = services.get_owner_domains(request.user)
        search = request.query_params.get("search")
        status_filter = request.query_params.get("status")
        if search:
            qs = qs.filter(domain__icontains=search)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return success_response(
            data={"domains": SendingDomainSerializer(qs, many=True).data},
        )

    @extend_schema(
        tags=["Domains"],
        request=SendingDomainCreateSerializer,
        summary="Add a sending domain",
    )
    def post(self, request):
        serializer = SendingDomainCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            domain = services.create_sending_domain(
                owner=request.user,
                **serializer.validated_data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"domain": SendingDomainSerializer(domain).data},
            message="Domain added successfully. Configure DNS records to verify.",
            status_code=status.HTTP_201_CREATED,
        )


class DomainDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageDomains, IsDomainOwner]

    def get_object(self, request, domain_id):
        domain = get_object_or_404(SendingDomain, id=domain_id, owner=request.user)
        self.check_object_permissions(request, domain)
        return domain

    @extend_schema(tags=["Domains"], summary="Get domain details")
    def get(self, request, domain_id):
        domain = self.get_object(request, domain_id)
        return success_response(data={"domain": SendingDomainSerializer(domain).data})

    @extend_schema(
        tags=["Domains"],
        request=SendingDomainUpdateSerializer,
        summary="Update domain",
    )
    def patch(self, request, domain_id):
        domain = self.get_object(request, domain_id)
        serializer = SendingDomainUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            domain = services.update_sending_domain(
                sending_domain=domain,
                **serializer.validated_data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"domain": SendingDomainSerializer(domain).data},
            message="Domain updated successfully.",
        )

    @extend_schema(tags=["Domains"], summary="Delete domain")
    def delete(self, request, domain_id):
        domain = self.get_object(request, domain_id)
        services.delete_sending_domain(sending_domain=domain)
        return success_response(message="Domain deleted successfully.")


class DomainSetDefaultView(APIView):
    permission_classes = [IsAuthenticated, CanManageDomains, IsDomainOwner]

    @extend_schema(tags=["Domains"], summary="Set domain as default")
    def post(self, request, domain_id):
        domain = get_object_or_404(SendingDomain, id=domain_id, owner=request.user)
        self.check_object_permissions(request, domain)

        try:
            domain = services.set_default_sending_domain(sending_domain=domain)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"domain": SendingDomainSerializer(domain).data},
            message="Default sending domain updated.",
        )


class DomainVerifyView(APIView):
    permission_classes = [IsAuthenticated, CanManageDomains, IsDomainOwner]

    @extend_schema(tags=["Domains"], summary="Verify domain DNS records")
    def post(self, request, domain_id):
        domain = get_object_or_404(SendingDomain, id=domain_id, owner=request.user)
        self.check_object_permissions(request, domain)

        success, message = services.verify_sending_domain(sending_domain=domain)
        return success_response(
            data={
                "success": success,
                "message": message,
                "domain": SendingDomainSerializer(domain).data,
            },
            message=message,
        )
