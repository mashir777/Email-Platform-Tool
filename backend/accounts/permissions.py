from rest_framework.permissions import BasePermission

from accounts.models import UserRole


class IsEmailVerified(BasePermission):
  message = "Email address must be verified to perform this action."

  def has_permission(self, request, view):
    return (
      request.user
      and request.user.is_authenticated
      and request.user.is_verified
    )


class HasRole(BasePermission):
  allowed_roles = set()
  message = "You do not have permission to perform this action."

  def has_permission(self, request, view):
    if not request.user or not request.user.is_authenticated:
      return False
    if request.user.is_superuser:
      return True
    return request.user.role in self.allowed_roles


class IsSuperAdmin(HasRole):
  allowed_roles = {UserRole.SUPER_ADMIN}


class IsAdmin(HasRole):
  allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


class IsManager(HasRole):
  allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER}


class IsClient(HasRole):
  allowed_roles = {
    UserRole.SUPER_ADMIN,
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.CLIENT,
  }


class IsOwnerOrAdmin(BasePermission):
  message = "You can only access your own resource."

  def has_object_permission(self, request, view, obj):
    if request.user.is_superuser or request.user.role in {
      UserRole.SUPER_ADMIN,
      UserRole.ADMIN,
    }:
      return True
    return obj == request.user
