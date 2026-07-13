from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from campaigns.models import Campaign
from subscribers.models import Subscriber
from tracking.models import TrackingEvent


class ReportsAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)
        self.campaign = Campaign.objects.create(
            owner=self.user,
            name="Launch",
            subject="Hello",
            status=Campaign.Status.SENT,
            sent_at=timezone.now(),
            recipient_count=100,
        )
        self.subscriber = Subscriber.objects.create(
            owner=self.user,
            email="sub@example.com",
        )
        for event_type in [
            TrackingEvent.EventType.SENT,
            TrackingEvent.EventType.DELIVERED,
            TrackingEvent.EventType.OPEN,
            TrackingEvent.EventType.CLICK,
            TrackingEvent.EventType.BOUNCE,
        ]:
            TrackingEvent.objects.create(
                owner=self.user,
                campaign=self.campaign,
                subscriber=self.subscriber,
                event_type=event_type,
            )

    def test_overview_endpoint(self):
        response = self.client.get(reverse("api:v1:reports:overview"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        overview = response.data["data"]["overview"]
        self.assertEqual(overview["sent"], 1)
        self.assertEqual(overview["opened"], 1)
        self.assertEqual(overview["campaigns_tracked"], 1)

    def test_campaign_reports_endpoint(self):
        response = self.client.get(reverse("api:v1:reports:campaigns"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reports = response.data["data"]["reports"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["campaign_name"], "Launch")
        self.assertEqual(reports[0]["opened"], 1)
        self.assertEqual(reports[0]["open_rate"], 100.0)

    def test_campaign_reports_search(self):
        response = self.client.get(
            reverse("api:v1:reports:campaigns"),
            {"search": "missing"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["reports"]), 0)
