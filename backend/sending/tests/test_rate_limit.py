from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from campaigns.models import Campaign
from core.encryption import encrypt_value
from sending.models import EmailQueueItem
from sending.services import (
    MIN_SEND_INTERVAL_SECONDS,
    can_send_email,
    compute_send_interval_seconds,
    run_pending_email_queue,
)
from sending.tasks import dispatch_campaign
from smtp_servers.models import SmtpServer
from subscribers.models import Subscriber, SubscriberList


class RateLimitTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.subscriber_list = SubscriberList.objects.create(
            owner=self.user,
            name="Newsletter",
        )
        self.smtp_server = SmtpServer.objects.create(
            owner=self.user,
            name="Test SMTP",
            host="mail.example.com",
            port=587,
            username="user",
            password_encrypted=encrypt_value("secret"),
            from_email="noreply@example.com",
            is_active=True,
            is_default=True,
            hourly_limit=60,
            daily_limit=1000,
        )
        self.campaign = Campaign.objects.create(
            owner=self.user,
            name="Welcome",
            subject="Hello",
            html_content="<p>Hi</p>",
            subscriber_list=self.subscriber_list,
        )

    def _add_subscriber(self, email: str):
        subscriber = Subscriber.objects.create(
            owner=self.user,
            email=email,
            status=Subscriber.Status.SUBSCRIBED,
        )
        subscriber.lists.add(self.subscriber_list)
        return subscriber

    def test_compute_send_interval_from_hourly_limit(self):
        self.assertEqual(compute_send_interval_seconds(self.smtp_server), 60)

        self.smtp_server.hourly_limit = 1
        self.assertEqual(compute_send_interval_seconds(self.smtp_server), 3600)

        self.smtp_server.hourly_limit = 120
        self.assertEqual(compute_send_interval_seconds(self.smtp_server), 30)

    def test_can_send_email_respects_hourly_limit(self):
        self.smtp_server.hourly_limit = 1
        self.smtp_server.save()

        EmailQueueItem.objects.create(
            owner=self.user,
            campaign=self.campaign,
            subscriber=self._add_subscriber("one@example.com"),
            smtp_server=self.smtp_server,
            to_email="one@example.com",
            status=EmailQueueItem.Status.SENT,
            sent_at=timezone.now(),
        )

        self.assertFalse(can_send_email(smtp_server=self.smtp_server))

    @patch("sending.services.send_message_via_smtp")
    def test_dispatch_campaign_uses_rate_limited_queue(self, mock_send):
        self._add_subscriber("one@gmail.com")
        self._add_subscriber("two@gmail.com")

        result = dispatch_campaign(str(self.campaign.id))

        self.assertTrue(result["ok"])
        self.assertEqual(result["queued"], 2)
        self.assertEqual(mock_send.call_count, 1)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, Campaign.Status.SENDING)
        self.assertEqual(
            EmailQueueItem.objects.filter(status=EmailQueueItem.Status.PENDING).count(),
            1,
        )

    @patch("sending.services.send_message_via_smtp")
    def test_run_pending_email_queue_sends_one_per_cycle(self, mock_send):
        sub_one = self._add_subscriber("one@gmail.com")
        sub_two = self._add_subscriber("two@gmail.com")

        EmailQueueItem.objects.create(
            owner=self.user,
            campaign=self.campaign,
            subscriber=sub_one,
            smtp_server=self.smtp_server,
            to_email=sub_one.email,
            status=EmailQueueItem.Status.PENDING,
        )
        EmailQueueItem.objects.create(
            owner=self.user,
            campaign=self.campaign,
            subscriber=sub_two,
            smtp_server=self.smtp_server,
            to_email=sub_two.email,
            status=EmailQueueItem.Status.PENDING,
        )
        self.campaign.status = Campaign.Status.SENDING
        self.campaign.save()

        first = run_pending_email_queue()
        self.assertEqual(first["processed"], 1)
        self.assertEqual(mock_send.call_count, 1)

        second = run_pending_email_queue()
        self.assertEqual(second["processed"], 0)
        self.assertEqual(mock_send.call_count, 1)

        past = timezone.now() - timedelta(seconds=MIN_SEND_INTERVAL_SECONDS + 1)
        EmailQueueItem.objects.filter(status=EmailQueueItem.Status.SENT).update(
            sent_at=past,
        )

        third = run_pending_email_queue()
        self.assertEqual(third["processed"], 1)
        self.assertEqual(mock_send.call_count, 2)
