from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsEmailVerified


class CanManageDomains(IsEmailVerified):
    message = "Email verification is required to manage domains."


class IsDomainOwner(IsAuthenticated):
    message = "You do not have permission to access this domain."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return obj.owner_id == request.user.id
