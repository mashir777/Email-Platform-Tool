from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsEmailVerified


class CanManageCampaigns(IsEmailVerified):
    message = "Email verification is required to manage campaigns."


class IsCampaignOwner(IsAuthenticated):
    message = "You do not have permission to access this campaign."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return obj.owner_id == request.user.id
