from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from core.encryption import decrypt_value, encrypt_value
from smtp_servers.models import SmtpServer


class SmtpServerAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_create_and_list_servers(self):
        response = self.client.post(
            reverse("api:v1:smtp:server-list"),
            {
                "name": "Mailgun",
                "host": "smtp.mailgun.org",
                "port": 587,
                "username": "postmaster@mg.example.com",
                "password": "secret-pass",
                "encryption": "tls",
                "from_email": "noreply@example.com",
                "from_name": "Example",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data["data"]["server"])
        self.assertNotIn("password_encrypted", response.data["data"]["server"])

        server = SmtpServer.objects.get()
        self.assertEqual(decrypt_value(server.password_encrypted), "secret-pass")

        list_response = self.client.get(reverse("api:v1:smtp:server-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["data"]["servers"]), 1)

    def test_update_server_without_changing_password(self):
        server = SmtpServer.objects.create(
            owner=self.user,
            name="Primary",
            host="smtp.example.com",
            port=587,
            username="user",
            password_encrypted=encrypt_value("old-pass"),
            from_email="noreply@example.com",
        )
        response = self.client.patch(
            reverse("api:v1:smtp:server-detail", args=[server.id]),
            {"name": "Primary Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        server.refresh_from_db()
        self.assertEqual(server.name, "Primary Updated")
        self.assertEqual(decrypt_value(server.password_encrypted), "old-pass")

    def test_set_default_server(self):
        first = SmtpServer.objects.create(
            owner=self.user,
            name="First",
            host="smtp1.example.com",
            port=587,
            from_email="a@example.com",
            is_default=True,
        )
        second = SmtpServer.objects.create(
            owner=self.user,
            name="Second",
            host="smtp2.example.com",
            port=587,
            from_email="b@example.com",
        )
        response = self.client.post(
            reverse("api:v1:smtp:set-default", args=[second.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    @patch("smtp_servers.services.smtplib.SMTP")
    def test_connection_test_success(self, mock_smtp):
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_smtp.return_value = mock_instance

        server = SmtpServer.objects.create(
            owner=self.user,
            name="Test SMTP",
            host="smtp.example.com",
            port=587,
            username="user",
            password_encrypted=encrypt_value("pass"),
            encryption=SmtpServer.Encryption.TLS,
            from_email="noreply@example.com",
        )
        response = self.client.post(
            reverse("api:v1:smtp:test", args=[server.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["success"])
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("user", "pass")

    def test_stats_endpoint(self):
        SmtpServer.objects.create(
            owner=self.user,
            name="A",
            host="smtp.example.com",
            port=587,
            from_email="a@example.com",
            is_active=True,
        )
        response = self.client.get(reverse("api:v1:smtp:stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["stats"]["total"], 1)
        self.assertEqual(response.data["data"]["stats"]["active"], 1)

    def test_delete_server(self):
        server = SmtpServer.objects.create(
            owner=self.user,
            name="Delete Me",
            host="smtp.example.com",
            port=587,
            from_email="a@example.com",
        )
        response = self.client.delete(
            reverse("api:v1:smtp:server-detail", args=[server.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(SmtpServer.objects.count(), 0)
