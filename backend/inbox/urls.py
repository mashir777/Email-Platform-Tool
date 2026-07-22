from django.urls import path

from inbox.views import (
    InboxMailboxDeleteView,
    InboxMailboxListCreateView,
    InboxMessageDetailView,
    InboxMessageListView,
    InboxMessageMarkReadView,
    InboxSyncView,
)

urlpatterns = [
    path("", InboxMessageListView.as_view(), name="inbox-list"),
    path("mailboxes/", InboxMailboxListCreateView.as_view(), name="inbox-mailboxes"),
    path("mailboxes/<uuid:mailbox_id>/", InboxMailboxDeleteView.as_view(), name="inbox-mailbox-delete"),
    path("sync/", InboxSyncView.as_view(), name="inbox-sync"),
    path("<uuid:message_id>/", InboxMessageDetailView.as_view(), name="inbox-detail"),
    path("<uuid:message_id>/read/", InboxMessageMarkReadView.as_view(), name="inbox-read"),
]
