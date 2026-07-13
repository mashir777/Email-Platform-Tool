from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from campaigns.models import Campaign
from core.encryption import encrypt_value
from sending.models import EmailQueueItem
from smtp_servers.models import SmtpServer
from subscribers.models import Subscriber, SubscriberList
from tracking.models import TrackingEvent


class CampaignSendAPITestCase(APITestCase):
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
        self.subscriber = Subscriber.objects.create(
            owner=self.user,
            email="sub@gmail.com",
            first_name="Sam",
            status=Subscriber.Status.SUBSCRIBED,
        )
        self.subscriber.lists.add(self.subscriber_list)
        self.campaign = Campaign.objects.create(
            owner=self.user,
            name="Welcome",
            subject="Hello {{first_name}}",
            html_content="<p>Hi {{first_name}}</p>",
            text_content="Hi {{first_name}}",
            from_email="noreply@example.com",
            from_name="Example",
            subscriber_list=self.subscriber_list,
        )
        SmtpServer.objects.create(
            owner=self.user,
            name="Test SMTP",
            host="mail.example.com",
            port=587,
            username="user",
            password_encrypted=encrypt_value("secret"),
            from_email="noreply@example.com",
            is_active=True,
            is_default=True,
        )

    @patch("sending.services.send_message_via_smtp")
    def test_send_campaign_now(self, mock_send):
        mock_send.return_value = None
        response = self.client.post(
            reverse("api:v1:campaigns:send", args=[self.campaign.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, Campaign.Status.SENT)
        self.assertIsNotNone(self.campaign.sent_at)
        self.assertEqual(self.campaign.recipient_count, 1)

        item = EmailQueueItem.objects.get(campaign=self.campaign)
        self.assertEqual(item.status, EmailQueueItem.Status.SENT)
        self.assertEqual(TrackingEvent.objects.filter(campaign=self.campaign).count(), 2)
        self.assertTrue(
            TrackingEvent.objects.filter(
                campaign=self.campaign,
                event_type=TrackingEvent.EventType.SENT,
            ).exists(),
        )
        self.assertTrue(
            TrackingEvent.objects.filter(
                campaign=self.campaign,
                event_type=TrackingEvent.EventType.DELIVERED,
            ).exists(),
        )
        mock_send.assert_called_once()

    def test_send_requires_content(self):
        empty = Campaign.objects.create(
            owner=self.user,
            name="Empty",
            subject="Hi",
            subscriber_list=self.subscriber_list,
        )
        response = self.client.post(
            reverse("api:v1:campaigns:send", args=[empty.id]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
