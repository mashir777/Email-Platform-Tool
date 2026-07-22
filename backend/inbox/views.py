from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified
from core.responses import error_response, success_response
from inbox.models import InboxMailbox, InboxMessage
from inbox.serializers import (
    InboxMailboxCreateSerializer,
    InboxMailboxSerializer,
    InboxMessageSerializer,
)
from inbox.services import create_inbox_mailbox, sync_inbox_mailbox, sync_owner_inboxes


class InboxMessageListView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(tags=["Unibox"], summary="List Unibox messages")
    def get(self, request):
        qs = (
            InboxMessage.objects.filter(owner=request.user)
            .select_related("mailbox", "smtp_server")
            .order_by("-received_at", "-created_at")
        )
        unread_only = request.query_params.get("unread") == "1"
        if unread_only:
            qs = qs.filter(is_read=False)
        limit = min(int(request.query_params.get("limit") or 100), 300)
        messages = list(qs[:limit])
        unread = InboxMessage.objects.filter(owner=request.user, is_read=False).count()
        return success_response(
            data={
                "messages": InboxMessageSerializer(messages, many=True).data,
                "unread_count": unread,
            },
        )


class InboxMailboxListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(tags=["Unibox"], summary="List Unibox mailboxes")
    def get(self, request):
        qs = InboxMailbox.objects.filter(owner=request.user)
        return success_response(
            data={"mailboxes": InboxMailboxSerializer(qs, many=True).data},
        )

    @extend_schema(tags=["Unibox"], summary="Add Unibox mailbox")
    def post(self, request):
        serializer = InboxMailboxCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            mailbox = create_inbox_mailbox(
                owner=request.user,
                email=data["email"],
                imap_host=data["imap_host"],
                username=data.get("username") or data["email"],
                password=data["password"],
                name=data.get("name") or "",
                imap_port=data.get("imap_port") or 993,
                verify_ssl=bool(data.get("verify_ssl")),
            )
        except ValidationError as exc:
            return error_response(exc.message_dict if hasattr(exc, "message_dict") else {"detail": [str(exc)]})
        # Pull replies immediately after add
        new_count = sync_inbox_mailbox(mailbox=mailbox)
        return success_response(
            data={
                "mailbox": InboxMailboxSerializer(mailbox).data,
                "new_messages": new_count,
            },
            message="Inbox added. Replies will appear here after sync.",
            status_code=status.HTTP_201_CREATED,
        )


class InboxMailboxDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(tags=["Unibox"], summary="Remove Unibox mailbox")
    def delete(self, request, mailbox_id):
        mailbox = get_object_or_404(InboxMailbox, id=mailbox_id, owner=request.user)
        mailbox.delete()
        return success_response(message="Inbox removed.")


class InboxSyncView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(tags=["Unibox"], summary="Sync IMAP inboxes into Unibox")
    def post(self, request):
        result = sync_owner_inboxes(owner=request.user)
        return success_response(
            data=result,
            message=f"Synced {result['new_messages']} new message(s).",
        )


class InboxMessageDetailView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(tags=["Unibox"], summary="Get a Unibox message")
    def get(self, request, message_id):
        msg = get_object_or_404(
            InboxMessage.objects.select_related("mailbox", "smtp_server"),
            id=message_id,
            owner=request.user,
        )
        return success_response(data={"message": InboxMessageSerializer(msg).data})

    @extend_schema(tags=["Unibox"], summary="Update a Unibox message")
    def patch(self, request, message_id):
        msg = get_object_or_404(InboxMessage, id=message_id, owner=request.user)
        if "is_read" in request.data:
            msg.is_read = bool(request.data.get("is_read"))
            msg.save(update_fields=["is_read", "updated_at"])
        return success_response(data={"message": InboxMessageSerializer(msg).data})


class InboxMessageMarkReadView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    @extend_schema(tags=["Unibox"], summary="Mark message read")
    def post(self, request, message_id):
        msg = get_object_or_404(InboxMessage, id=message_id, owner=request.user)
        msg.is_read = True
        msg.save(update_fields=["is_read", "updated_at"])
        return success_response(data={"message": InboxMessageSerializer(msg).data})
