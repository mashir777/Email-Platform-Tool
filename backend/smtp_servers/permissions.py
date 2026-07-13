from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsEmailVerified


class CanManageSmtpServers(IsEmailVerified):
    message = "Email verification is required to manage SMTP servers."


class IsSmtpServerOwner(IsAuthenticated):
    message = "You do not have permission to access this SMTP server."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return obj.owner_id == request.user.id
