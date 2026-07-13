from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from campaigns.models import Campaign
from subscribers.models import Subscriber, SubscriberList


class CampaignAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)
        self.subscriber_list = SubscriberList.objects.create(
            owner=self.user,
            name="Newsletter",
        )
        sub = Subscriber.objects.create(
            owner=self.user,
            email="sub@example.com",
            status=Subscriber.Status.SUBSCRIBED,
        )
        sub.lists.add(self.subscriber_list)

    def test_create_and_list_campaigns(self):
        response = self.client.post(
            reverse("api:v1:campaigns:campaign-list"),
            {
                "name": "Welcome Series",
                "subject": "Hello!",
                "subscriber_list_id": str(self.subscriber_list.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get(reverse("api:v1:campaigns:campaign-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["data"]["campaigns"]), 1)

    def test_schedule_campaign(self):
        campaign = Campaign.objects.create(
            owner=self.user,
            name="Launch",
            subject="We are live",
            subscriber_list=self.subscriber_list,
        )
        scheduled_at = timezone.now() + timedelta(hours=2)
        response = self.client.post(
            reverse("api:v1:campaigns:schedule", args=[campaign.id]),
            {"scheduled_at": scheduled_at.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["campaign"]["status"],
            Campaign.Status.SCHEDULED,
        )

    def test_cancel_scheduled_campaign(self):
        campaign = Campaign.objects.create(
            owner=self.user,
            name="Cancel Me",
            subject="Test",
            status=Campaign.Status.SCHEDULED,
            subscriber_list=self.subscriber_list,
            scheduled_at=timezone.now() + timedelta(hours=1),
        )
        response = self.client.post(
            reverse("api:v1:campaigns:cancel", args=[campaign.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["campaign"]["status"],
            Campaign.Status.CANCELLED,
        )

    def test_duplicate_campaign(self):
        campaign = Campaign.objects.create(
            owner=self.user,
            name="Original",
            subject="Hello",
            html_content="<p>Hi</p>",
        )
        response = self.client.post(
            reverse("api:v1:campaigns:duplicate", args=[campaign.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("Copy", response.data["data"]["campaign"]["name"])

    def test_stats_endpoint(self):
        Campaign.objects.create(owner=self.user, name="A", subject="S")
        response = self.client.get(reverse("api:v1:campaigns:stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["stats"]["total"], 1)
