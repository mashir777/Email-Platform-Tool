from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from campaigns.models import Campaign
from core.encryption import encrypt_value
from sending.models import EmailQueueItem
from smtp_servers.models import SmtpServer
from subscribers.models import Subscriber, SubscriberList
from tracking.models import TrackingEvent
from tracking.services import inject_open_tracking_pixel
from tracking.tokens import make_open_token


class TrackingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.subscriber_list = SubscriberList.objects.create(owner=self.user, name="List")
        self.subscriber = Subscriber.objects.create(
            owner=self.user,
            email="user@gmail.com",
            status=Subscriber.Status.SUBSCRIBED,
        )
        self.subscriber.lists.add(self.subscriber_list)
        self.campaign = Campaign.objects.create(
            owner=self.user,
            name="Test",
            subject="Hi",
            html_content="<html><body><p>Hello</p></body></html>",
            subscriber_list=self.subscriber_list,
            status=Campaign.Status.SENT,
        )
        self.smtp_server = SmtpServer.objects.create(
            owner=self.user,
            name="SMTP",
            host="mail.example.com",
            port=465,
            username="info@example.com",
            password_encrypted=encrypt_value("secret"),
            encryption=SmtpServer.Encryption.SSL,
            from_email="info@example.com",
            is_active=True,
        )
        self.queue_item = EmailQueueItem.objects.create(
            owner=self.user,
            campaign=self.campaign,
            subscriber=self.subscriber,
            smtp_server=self.smtp_server,
            to_email=self.subscriber.email,
            status=EmailQueueItem.Status.SENT,
            sent_at=timezone.now(),
        )
        self.client = Client()

    def test_inject_open_tracking_pixel(self):
        html = inject_open_tracking_pixel(
            self.campaign.html_content,
            str(self.queue_item.id),
            campaign_id=str(self.campaign.id),
        )
        self.assertIn("/t/open/", html)
        self.assertIn("/t/view/", html)
        self.assertIn("Confirm you received this email", html)
        self.assertIn(make_open_token(str(self.queue_item.id)), html)

    def test_view_link_records_open(self):
        token = make_open_token(str(self.queue_item.id))
        response = self.client.get(f"/t/view/{token}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            TrackingEvent.objects.filter(
                campaign=self.campaign,
                event_type=TrackingEvent.EventType.OPEN,
            ).exists(),
        )

    def test_open_pixel_records_event(self):
        token = make_open_token(str(self.queue_item.id))
        response = self.client.get(f"/t/open/{token}.gif")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/gif")
        self.assertTrue(
            TrackingEvent.objects.filter(
                campaign=self.campaign,
                subscriber=self.subscriber,
                event_type=TrackingEvent.EventType.OPEN,
            ).exists(),
        )
