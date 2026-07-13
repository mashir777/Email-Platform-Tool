from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error_response, success_response
from smtp_servers import import_services, services
from smtp_servers.models import SmtpServer
from smtp_servers.permissions import CanManageSmtpServers, IsSmtpServerOwner
from smtp_servers.serializers import (
    SmtpServerCreateSerializer,
    SmtpServerSerializer,
    SmtpServerUpdateSerializer,
    SmtpStatsSerializer,
)


class SmtpStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["SMTP"], summary="Get SMTP server statistics")
    def get(self, request):
        stats = services.get_smtp_stats(request.user)
        return success_response(data={"stats": SmtpStatsSerializer(stats).data})


class SmtpServerCollectionView(APIView):
    permission_classes = [IsAuthenticated, CanManageSmtpServers]

    @extend_schema(tags=["SMTP"], summary="List SMTP servers")
    def get(self, request):
        qs = services.get_owner_smtp_servers(request.user)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(host__icontains=search)
        return success_response(
            data={"servers": SmtpServerSerializer(qs, many=True).data},
        )

    @extend_schema(
        tags=["SMTP"],
        request=SmtpServerCreateSerializer,
        summary="Create an SMTP server",
    )
    def post(self, request):
        serializer = SmtpServerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        password = data.pop("password", "")

        try:
            server = services.create_smtp_server(
                owner=request.user,
                password=password,
                **data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"server": SmtpServerSerializer(server).data},
            message="SMTP server created successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class SmtpServerDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageSmtpServers, IsSmtpServerOwner]

    def get_object(self, request, server_id):
        server = get_object_or_404(SmtpServer, id=server_id, owner=request.user)
        self.check_object_permissions(request, server)
        return server

    @extend_schema(tags=["SMTP"], summary="Get SMTP server details")
    def get(self, request, server_id):
        server = self.get_object(request, server_id)
        return success_response(data={"server": SmtpServerSerializer(server).data})

    @extend_schema(
        tags=["SMTP"],
        request=SmtpServerUpdateSerializer,
        summary="Update SMTP server",
    )
    def patch(self, request, server_id):
        server = self.get_object(request, server_id)
        serializer = SmtpServerUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        password = data.pop("password", None)

        try:
            server = services.update_smtp_server(
                smtp_server=server,
                password=password if password else None,
                **data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"server": SmtpServerSerializer(server).data},
            message="SMTP server updated successfully.",
        )

    @extend_schema(tags=["SMTP"], summary="Delete SMTP server")
    def delete(self, request, server_id):
        server = self.get_object(request, server_id)
        services.delete_smtp_server(smtp_server=server)
        return success_response(message="SMTP server deleted successfully.")


class SmtpServerSetDefaultView(APIView):
    permission_classes = [IsAuthenticated, CanManageSmtpServers, IsSmtpServerOwner]

    @extend_schema(tags=["SMTP"], summary="Set SMTP server as default")
    def post(self, request, server_id):
        server = get_object_or_404(SmtpServer, id=server_id, owner=request.user)
        self.check_object_permissions(request, server)

        try:
            server = services.set_default_smtp_server(smtp_server=server)
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"server": SmtpServerSerializer(server).data},
            message="Default SMTP server updated.",
        )


class SmtpServerTestView(APIView):
    permission_classes = [IsAuthenticated, CanManageSmtpServers, IsSmtpServerOwner]

    @extend_schema(tags=["SMTP"], summary="Test SMTP server connection")
    def post(self, request, server_id):
        server = get_object_or_404(SmtpServer, id=server_id, owner=request.user)
        self.check_object_permissions(request, server)

        success, message = services.test_smtp_connection(smtp_server=server)
        return success_response(
            data={
                "success": success,
                "message": message,
                "server": SmtpServerSerializer(server).data,
            },
            message=message,
        )


class SmtpServerImportView(APIView):
    permission_classes = [IsAuthenticated, CanManageSmtpServers]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=["SMTP"], summary="Import SMTP servers from CSV")
    def post(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return error_response(
                {"file": ["CSV file is required."]},
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = import_services.import_smtp_servers_from_csv(
                owner=request.user,
                csv_file=csv_file,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        message = (
            f"Imported {result['created']} server(s), updated {result['updated']}, "
            f"skipped {result['skipped']}."
        )
        return success_response(data={"import": result}, message=message)
