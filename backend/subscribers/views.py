from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error_response, success_response
from subscribers import services
from subscribers.models import Subscriber, SubscriberList
from subscribers.permissions import CanManageSubscribers, IsSubscriberOwner
from subscribers.serializers import (
    SubscriberBulkDeleteSerializer,
    SubscriberCreateSerializer,
    SubscriberImportSerializer,
    SubscriberListCreateSerializer,
    SubscriberListSerializer,
    SubscriberListUpdateSerializer,
    SubscriberListVerifySerializer,
    SubscriberSerializer,
    SubscriberStatsSerializer,
    SubscriberUpdateSerializer,
)


class SubscriberStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Subscribers"], summary="Get subscriber statistics")
    def get(self, request):
        qs = services.get_owner_subscribers(request.user)
        stats = {
            "total": qs.count(),
            "subscribed": qs.filter(status=Subscriber.Status.SUBSCRIBED).count(),
            "unsubscribed": qs.filter(status=Subscriber.Status.UNSUBSCRIBED).count(),
            "bounced": qs.filter(status=Subscriber.Status.BOUNCED).count(),
            "complained": qs.filter(status=Subscriber.Status.COMPLAINED).count(),
            "lists": services.get_owner_lists(request.user).count(),
        }
        return success_response(data={"stats": SubscriberStatsSerializer(stats).data})


class SubscriberListListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanManageSubscribers()]

    @extend_schema(tags=["Subscribers"], summary="List subscriber lists")
    def get(self, request):
        lists = services.get_owner_lists(request.user)
        return success_response(
            data={"lists": SubscriberListSerializer(lists, many=True).data},
        )

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberListCreateSerializer,
        summary="Create a subscriber list",
    )
    def post(self, request):
        serializer = SubscriberListCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            subscriber_list = services.create_list(
                owner=request.user,
                **serializer.validated_data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"list": SubscriberListSerializer(subscriber_list).data},
            message="List created successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class SubscriberListDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers]

    def get_object(self, request, list_id):
        return get_object_or_404(SubscriberList, id=list_id, owner=request.user)

    @extend_schema(tags=["Subscribers"], summary="Get subscriber list details")
    def get(self, request, list_id):
        subscriber_list = self.get_object(request, list_id)
        return success_response(
            data={"list": SubscriberListSerializer(subscriber_list).data},
        )

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberListUpdateSerializer,
        summary="Update subscriber list",
    )
    def patch(self, request, list_id):
        subscriber_list = self.get_object(request, list_id)
        serializer = SubscriberListUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            subscriber_list = services.update_list(
                subscriber_list=subscriber_list,
                **serializer.validated_data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"list": SubscriberListSerializer(subscriber_list).data},
            message="List updated successfully.",
        )

    @extend_schema(tags=["Subscribers"], summary="Delete subscriber list")
    def delete(self, request, list_id):
        subscriber_list = self.get_object(request, list_id)
        services.delete_list(subscriber_list=subscriber_list)
        return success_response(message="List deleted successfully.")


class SubscriberCollectionView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers]

    @extend_schema(tags=["Subscribers"], summary="List subscribers")
    def get(self, request):
        qs = services.get_owner_subscribers(request.user)

        list_id = request.query_params.get("list_id")
        status_filter = request.query_params.get("status")
        search = request.query_params.get("search")

        if list_id:
            qs = qs.filter(lists__id=list_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(email__icontains=search) | qs.filter(
                first_name__icontains=search,
            ) | qs.filter(last_name__icontains=search)

        serializer_context = {"owner": request.user}
        if list_id:
            serializer_context["subscriber_list"] = get_object_or_404(
                SubscriberList,
                id=list_id,
                owner=request.user,
            )

        return success_response(
            data={
                "subscribers": SubscriberSerializer(
                    qs.distinct(),
                    many=True,
                    context=serializer_context,
                ).data,
            },
        )

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberCreateSerializer,
        summary="Create a subscriber",
    )
    def post(self, request):
        serializer = SubscriberCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        list_ids = data.pop("list_ids", [])

        try:
            subscriber = services.create_subscriber(
                owner=request.user,
                list_ids=list_ids,
                **data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"subscriber": SubscriberSerializer(subscriber).data},
            message="Subscriber created successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class SubscriberDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers, IsSubscriberOwner]

    def get_object(self, request, subscriber_id):
        subscriber = get_object_or_404(
            Subscriber.objects.prefetch_related("lists"),
            id=subscriber_id,
            owner=request.user,
        )
        self.check_object_permissions(request, subscriber)
        return subscriber

    @extend_schema(tags=["Subscribers"], summary="Get subscriber details")
    def get(self, request, subscriber_id):
        subscriber = self.get_object(request, subscriber_id)
        return success_response(
            data={"subscriber": SubscriberSerializer(subscriber).data},
        )

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberUpdateSerializer,
        summary="Update subscriber",
    )
    def patch(self, request, subscriber_id):
        subscriber = self.get_object(request, subscriber_id)
        serializer = SubscriberUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        list_ids = data.pop("list_ids", None)

        try:
            subscriber = services.update_subscriber(
                subscriber=subscriber,
                list_ids=list_ids,
                **data,
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"subscriber": SubscriberSerializer(subscriber).data},
            message="Subscriber updated successfully.",
        )

    @extend_schema(tags=["Subscribers"], summary="Delete subscriber")
    def delete(self, request, subscriber_id):
        subscriber = self.get_object(request, subscriber_id)
        services.delete_subscriber(subscriber=subscriber)
        return success_response(message="Subscriber deleted successfully.")


class SubscriberBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers]

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberBulkDeleteSerializer,
        summary="Bulk delete subscribers",
    )
    def post(self, request):
        serializer = SubscriberBulkDeleteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        deleted = services.bulk_delete_subscribers(
            owner=request.user,
            subscriber_ids=serializer.validated_data["ids"],
        )
        return success_response(
            data={"deleted": deleted},
            message="Subscribers deleted successfully.",
        )


class SubscriberImportView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberImportSerializer,
        summary="Import subscribers from CSV",
    )
    def post(self, request):
        serializer = SubscriberImportSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            result = services.import_subscribers_from_csv(
                owner=request.user,
                csv_file=serializer.validated_data["file"],
                list_id=serializer.validated_data.get("list_id"),
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"import": result},
            message="Import completed successfully.",
        )


class SubscriberVerifyListView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers]

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberListVerifySerializer,
        summary="Verify emails on a list with Reacher and remove invalid ones in place",
    )
    def post(self, request):
        serializer = SubscriberListVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            result = services.verify_list_with_reacher(
                owner=request.user,
                list_id=serializer.validated_data["list_id"],
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"verify": result},
            message="List verification completed.",
        )


class SubscriberFilterCsvView(APIView):
    permission_classes = [IsAuthenticated, CanManageSubscribers]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Subscribers"],
        request=SubscriberImportSerializer,
        summary="Import CSV and filter emails with Reacher (check-if-email-exists)",
    )
    def post(self, request):
        serializer = SubscriberImportSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)

        try:
            result = services.import_and_filter_csv_with_reacher(
                owner=request.user,
                csv_file=serializer.validated_data["file"],
                list_id=serializer.validated_data.get("list_id"),
            )
        except ValidationError as exc:
            return error_response(exc.message_dict, status.HTTP_400_BAD_REQUEST)

        return success_response(
            data={"filter": result},
            message="CSV import and Reacher filter completed.",
        )
