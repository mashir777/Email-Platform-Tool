from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsEmailVerified


class IsSubscriberOwner(IsAuthenticated):
    """Ensures the user owns the subscriber resource."""

    message = "You do not have permission to access this subscriber."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return obj.owner_id == request.user.id


class CanManageSubscribers(IsEmailVerified):
    """Verified users can manage subscribers."""

    message = "Email verification is required to manage subscribers."
