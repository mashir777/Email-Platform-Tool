from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from campaigns.models import Campaign
from sending.models import EmailQueueItem
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

    def test_daily_report_attributes_late_open_to_send_day(self):
        sent_day = timezone.now() - timezone.timedelta(days=2)
        later_open = timezone.now()
        queue_item = EmailQueueItem.objects.create(
            owner=self.user,
            campaign=self.campaign,
            subscriber=self.subscriber,
            to_email=self.subscriber.email,
            status=EmailQueueItem.Status.SENT,
            sent_at=sent_day,
        )
        open_event = TrackingEvent.objects.create(
            owner=self.user,
            campaign=self.campaign,
            subscriber=self.subscriber,
            event_type=TrackingEvent.EventType.OPEN,
            metadata={
                "queue_item_id": str(queue_item.id),
                "to_email": self.subscriber.email,
            },
        )
        TrackingEvent.objects.filter(pk=open_event.pk).update(created_at=later_open)

        response = self.client.get(reverse("api:v1:reports:daily"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        days = response.data["data"]["daily"]["days"]
        send_date = timezone.localtime(sent_day).date().isoformat()
        day_row = next((row for row in days if row["date"] == send_date), None)
        self.assertIsNotNone(day_row)
        self.assertEqual(day_row["sent"], 1)
        self.assertEqual(day_row["opened"], 1)
        self.assertEqual(day_row["waiting"], 0)

        detail = self.client.get(
            reverse("api:v1:reports:daily-detail", kwargs={"day": send_date}),
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        emails = detail.data["data"]["day"]["emails"]
        self.assertEqual(len(emails), 1)
        self.assertTrue(emails[0]["opened"])
        self.assertEqual(emails[0]["status"], "opened")
