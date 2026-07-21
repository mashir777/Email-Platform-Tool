import hashlib
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole, UserToken
from accounts.services import _create_user_token, register_user


class AuthAPITestCase(APITestCase):
    def setUp(self):
        self.password = "SecurePass123!"
        self.user = User.objects.create_user(
            email="user@example.com",
            password=self.password,
            username="user",
            first_name="Test",
            last_name="User",
            is_verified=True,
        )

    def _auth_header(self, user=None):
        user = user or self.user
        token = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}

    def test_register_success(self):
        response = self.client.post(
            reverse("api:v1:accounts:register"),
            {
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "New",
                "last_name": "User",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("tokens", response.data["data"])
        self.assertEqual(response.data["data"]["user"]["role"], UserRole.CLIENT)
        self.assertTrue(response.data["data"]["user"]["is_verified"])

    def test_register_duplicate_email(self):
        response = self.client.post(
            reverse("api:v1:accounts:register"),
            {
                "email": self.user.email,
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_login_success(self):
        response = self.client.post(
            reverse("api:v1:accounts:login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["data"]["tokens"])

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("api:v1:accounts:login"),
            {"email": self.user.email, "password": "WrongPassword1!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            reverse("api:v1:accounts:logout"),
            {"refresh": str(refresh)},
            format="json",
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            reverse("api:v1:accounts:token-refresh"),
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["data"]["tokens"])

    def test_forgot_password_always_returns_success(self):
        response = self.client.post(
            reverse("api:v1:accounts:password-forgot"),
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        unknown = self.client.post(
            reverse("api:v1:accounts:password-forgot"),
            {"email": "unknown@example.com"},
            format="json",
        )
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)

    def test_reset_password(self):
        raw_token, _ = _create_user_token(
            self.user,
            UserToken.TokenType.PASSWORD_RESET,
            lifetime_hours=2,
        )
        response = self.client.post(
            reverse("api:v1:accounts:password-reset"),
            {
                "token": raw_token,
                "password": "NewSecurePass1!",
                "password_confirm": "NewSecurePass1!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass1!"))

    def test_change_password(self):
        response = self.client.post(
            reverse("api:v1:accounts:password-change"),
            {
                "old_password": self.password,
                "password": "NewSecurePass1!",
                "password_confirm": "NewSecurePass1!",
            },
            format="json",
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass1!"))

    def test_change_password_requires_verified_email(self):
        self.user.is_verified = False
        self.user.save()
        response = self.client.post(
            reverse("api:v1:accounts:password-change"),
            {
                "old_password": self.password,
                "password": "NewSecurePass1!",
                "password_confirm": "NewSecurePass1!",
            },
            format="json",
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verify_email(self):
        self.user.is_verified = False
        self.user.save()
        raw_token, _ = _create_user_token(
            self.user,
            UserToken.TokenType.EMAIL_VERIFICATION,
            lifetime_hours=24,
        )
        response = self.client.post(
            reverse("api:v1:accounts:email-verify"),
            {"token": raw_token},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)

    def test_resend_verification(self):
        self.user.is_verified = False
        self.user.save()
        response = self.client.post(
            reverse("api:v1:accounts:email-resend"),
            format="json",
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_profile(self):
        response = self.client.get(
            reverse("api:v1:accounts:profile"),
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["user"]["email"], self.user.email)

    def test_update_profile(self):
        response = self.client.patch(
            reverse("api:v1:accounts:profile"),
            {"first_name": "Updated", "company_name": "Acme Corp"},
            format="json",
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.company_name, "Acme Corp")

    def test_upload_avatar(self):
        image = SimpleUploadedFile(
            "avatar.png",
            BytesIO(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            ).getvalue(),
            content_type="image/png",
        )
        response = self.client.post(
            reverse("api:v1:accounts:avatar"),
            {"avatar": image},
            format="multipart",
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))

    def test_roles_list(self):
        response = self.client.get(
            reverse("api:v1:accounts:roles"),
            **self._auth_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        roles = {r["value"] for r in response.data["data"]["roles"]}
        self.assertEqual(
            roles,
            {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.CLIENT},
        )


class PermissionsTestCase(APITestCase):
    def test_role_properties(self):
        super_admin = User.objects.create_user(
            email="super@example.com",
            password="SecurePass123!",
            username="super",
            role=UserRole.SUPER_ADMIN,
        )
        admin = User.objects.create_user(
            email="admin@example.com",
            password="SecurePass123!",
            username="admin",
            role=UserRole.ADMIN,
        )
        manager = User.objects.create_user(
            email="manager@example.com",
            password="SecurePass123!",
            username="manager",
            role=UserRole.MANAGER,
        )
        client = User.objects.create_user(
            email="client@example.com",
            password="SecurePass123!",
            username="client",
            role=UserRole.CLIENT,
        )

        self.assertTrue(super_admin.is_super_admin)
        self.assertTrue(admin.is_admin)
        self.assertFalse(client.is_admin)
        self.assertTrue(manager.is_manager)
        self.assertFalse(client.is_manager)


class ServicesTestCase(APITestCase):
    def test_register_user_is_verified_on_signup(self):
        user = register_user(
            email="service@example.com",
            password="SecurePass123!",
        )
        self.assertEqual(user.role, UserRole.CLIENT)
        self.assertTrue(user.is_verified)

    def test_token_hash_is_stored_not_plaintext(self):
        user = User.objects.create_user(
            email="token@example.com",
            password="SecurePass123!",
            username="tokenuser",
        )
        raw_token, user_token = _create_user_token(
            user,
            UserToken.TokenType.EMAIL_VERIFICATION,
            lifetime_hours=1,
        )
        self.assertNotEqual(user_token.token_hash, raw_token)
        self.assertEqual(
            user_token.token_hash,
            hashlib.sha256(raw_token.encode()).hexdigest(),
        )
