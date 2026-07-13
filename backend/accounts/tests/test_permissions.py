from django.test import RequestFactory, TestCase

from accounts.models import User, UserRole
from accounts.permissions import IsAdmin, IsEmailVerified, IsManager, IsSuperAdmin


class PermissionClassesTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.super_admin = User.objects.create_user(
            email="super@example.com",
            password="SecurePass123!",
            username="super",
            role=UserRole.SUPER_ADMIN,
            is_verified=True,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="SecurePass123!",
            username="admin",
            role=UserRole.ADMIN,
            is_verified=True,
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="SecurePass123!",
            username="manager",
            role=UserRole.MANAGER,
            is_verified=True,
        )
        self.client_user = User.objects.create_user(
            email="client@example.com",
            password="SecurePass123!",
            username="client",
            role=UserRole.CLIENT,
            is_verified=False,
        )

    def _request_for(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_is_super_admin_permission(self):
        permission = IsSuperAdmin()
        self.assertTrue(permission.has_permission(self._request_for(self.super_admin), None))
        self.assertFalse(permission.has_permission(self._request_for(self.admin), None))

    def test_is_admin_permission(self):
        permission = IsAdmin()
        self.assertTrue(permission.has_permission(self._request_for(self.admin), None))
        self.assertFalse(permission.has_permission(self._request_for(self.manager), None))

    def test_is_manager_permission(self):
        permission = IsManager()
        self.assertTrue(permission.has_permission(self._request_for(self.manager), None))
        self.assertFalse(permission.has_permission(self._request_for(self.client_user), None))

    def test_is_email_verified_permission(self):
        permission = IsEmailVerified()
        self.assertTrue(permission.has_permission(self._request_for(self.admin), None))
        self.assertFalse(permission.has_permission(self._request_for(self.client_user), None))
