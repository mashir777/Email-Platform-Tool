from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from domains.models import SendingDomain


class DomainAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_create_and_list_domains(self):
        response = self.client.post(
            reverse("api:v1:domains:domain-list"),
            {"domain": "example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["domain"]["domain"], "example.com")
        self.assertEqual(len(response.data["data"]["domain"]["dns_records"]), 4)

        list_response = self.client.get(reverse("api:v1:domains:domain-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["data"]["domains"]), 1)

    def test_duplicate_domain_rejected(self):
        SendingDomain.objects.create(
            owner=self.user,
            domain="example.com",
            verification_token="abc",
        )
        response = self.client.post(
            reverse("api:v1:domains:domain-list"),
            {"domain": "example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("domains.services._txt_records")
    def test_verify_domain_success(self, mock_txt):
        def txt_side_effect(host):
            if host == "_emailplatform-verify.example.com":
                return ["emailplatform-verify=token123"]
            if host == "example.com":
                return ["v=spf1 include:spf.emailplatform.com ~all"]
            if host == "epmail._domainkey.example.com":
                return ["v=DKIM1; k=rsa; p=publickeybody"]
            if host == "_dmarc.example.com":
                return ["v=DMARC1; p=none"]
            return []

        mock_txt.side_effect = txt_side_effect

        domain = SendingDomain.objects.create(
            owner=self.user,
            domain="example.com",
            verification_token="token123",
            dkim_public_key="publickeybody",
        )
        response = self.client.post(
            reverse("api:v1:domains:verify", args=[domain.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["success"])
        domain.refresh_from_db()
        self.assertEqual(domain.status, SendingDomain.Status.VERIFIED)
        self.assertTrue(domain.is_active)
        self.assertTrue(domain.is_default)

    @patch("domains.services._txt_records")
    def test_verify_domain_relaxed_when_spf_present(self, mock_txt):
        def txt_side_effect(host):
            if host == "relaxed.example.com":
                return ["v=spf1 include:mail.example.com ~all"]
            if host == "_dmarc.relaxed.example.com":
                return ["v=DMARC1; p=none"]
            return []

        mock_txt.side_effect = txt_side_effect

        domain = SendingDomain.objects.create(
            owner=self.user,
            domain="relaxed.example.com",
            verification_token="token123",
            dkim_public_key="publickeybody",
        )
        with self.settings(DOMAIN_RELAXED_VERIFICATION=True):
            response = self.client.post(
                reverse("api:v1:domains:verify", args=[domain.id]),
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["success"])
        domain.refresh_from_db()
        self.assertEqual(domain.status, SendingDomain.Status.VERIFIED)
        self.assertTrue(domain.is_active)

    @patch("domains.services._txt_records")
    def test_verify_domain_ownership_on_apex_txt(self, mock_txt):
        def txt_side_effect(host):
            if host == "apex.example.com":
                return [
                    "v=spf1 include:mail.example.com ~all",
                    "emailplatform-verify=token123",
                ]
            return []

        mock_txt.side_effect = txt_side_effect

        domain = SendingDomain.objects.create(
            owner=self.user,
            domain="apex.example.com",
            verification_token="token123",
            dkim_public_key="publickeybody",
        )
        response = self.client.post(
            reverse("api:v1:domains:verify", args=[domain.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["success"])
        domain.refresh_from_db()
        self.assertEqual(domain.status, SendingDomain.Status.VERIFIED)

    def test_set_default_requires_verified(self):
        domain = SendingDomain.objects.create(
            owner=self.user,
            domain="pending.com",
            verification_token="abc",
            status=SendingDomain.Status.PENDING,
        )
        response = self.client.post(
            reverse("api:v1:domains:set-default", args=[domain.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stats_endpoint(self):
        SendingDomain.objects.create(
            owner=self.user,
            domain="a.com",
            verification_token="t1",
            status=SendingDomain.Status.VERIFIED,
        )
        response = self.client.get(reverse("api:v1:domains:stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["stats"]["total"], 1)
        self.assertEqual(response.data["data"]["stats"]["verified"], 1)

    def test_delete_domain(self):
        domain = SendingDomain.objects.create(
            owner=self.user,
            domain="delete.com",
            verification_token="abc",
        )
        response = self.client.delete(
            reverse("api:v1:domains:domain-detail", args=[domain.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(SendingDomain.objects.count(), 0)
