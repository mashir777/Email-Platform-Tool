from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from campaigns.models import Campaign
from core.encryption import encrypt_value
from sending.models import EmailQueueItem
from sending.services import _format_html_message, _personalize
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

    @patch("sending.services.send_message_via_smtp")
    def test_csv_reimport_allows_resend_to_same_subscriber(self, mock_send):
        mock_send.return_value = None
        from sending.services import queue_campaign

        self.client.post(
            reverse("api:v1:campaigns:send", args=[self.campaign.id]),
            format="json",
        )
        self.assertEqual(
            EmailQueueItem.objects.get(campaign=self.campaign).status,
            EmailQueueItem.Status.SENT,
        )

        campaign_two = Campaign.objects.create(
            owner=self.user,
            name="Welcome again",
            subject="Hello again",
            html_content="<p>Hi again</p>",
            from_email="noreply@example.com",
            from_name="Example",
            subscriber_list=self.subscriber_list,
        )
        queued_before_reimport = queue_campaign(campaign=campaign_two)
        self.assertEqual(queued_before_reimport, 0)
        self.assertEqual(
            EmailQueueItem.objects.get(campaign=campaign_two).status,
            EmailQueueItem.Status.SKIPPED,
        )

        import io

        from subscribers.services import import_subscribers_from_csv

        csv_content = "email,first_name\nsub@gmail.com,Sam\n"
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "Newsletter.csv"
        import_subscribers_from_csv(
            owner=self.user,
            csv_file=csv_file,
            list_id=str(self.subscriber_list.id),
        )

        campaign_three = Campaign.objects.create(
            owner=self.user,
            name="After CSV re-import",
            subject="Hello again",
            html_content="<p>Hi again</p>",
            from_email="noreply@example.com",
            from_name="Example",
            subscriber_list=self.subscriber_list,
        )
        queued_after_reimport = queue_campaign(campaign=campaign_three)
        self.assertEqual(queued_after_reimport, 1)
        self.assertEqual(
            EmailQueueItem.objects.get(campaign=campaign_three).status,
            EmailQueueItem.Status.PENDING,
        )

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

    def test_personalize_uses_standard_and_any_csv_fields(self):
        self.subscriber.company = "Acme SaaS"
        self.subscriber.industrial_company = "Software"
        self.subscriber.custom_fields = {
            "Job Title": "Founder",
            "City": "Lahore",
        }
        self.subscriber.save()

        message = (
            "Hi [First Name], {{Company Name}} serves {{Industrial Company}}. "
            "Role: {{Job Title}}, city: [City]."
        )
        self.assertEqual(
            _personalize(message, self.subscriber),
            "Hi Sam, Acme SaaS serves Software. Role: Founder, city: Lahore.",
        )

    def test_personalize_sender_name_placeholder_and_hardcoded_swap(self):
        message = "Best,\nDavid Wilson\nDatrix World\n— {{sender_name}}"
        result = _personalize(
            message,
            self.subscriber,
            sender_name="Ava Jackson",
            sender_names_to_swap=["David Wilson", "Oliver Wilson", "Ava Jackson"],
        )
        self.assertEqual(
            result,
            "Best,\nAva Jackson\nDatrix World\n— Ava Jackson",
        )

    def test_personalize_rewrites_hardcoded_signature_from_sender_from_name(self):
        html = (
            "Just curious.<br><br> Best,<br> David Wilson<br> "
            "Datrix World | datrixworld.com"
        )
        result = _personalize(
            html,
            self.subscriber,
            sender_name="Chloe Clark",
            sender_names_to_swap=["Ava Jackson", "Chloe Clark"],
        )
        self.assertIn("Best,<br> Chloe Clark<br>", result)
        self.assertNotIn("David Wilson", result)

    def test_plain_text_message_is_formatted_as_readable_html(self):
        formatted = _format_html_message("Hi Sam,\n\nHow are you?\n\nBest,\nDavid")
        self.assertIn('data-email-body="true"', formatted)
        self.assertIn("Hi Sam,<br>\n<br>\nHow are you?", formatted)
        self.assertIn("line-height:1.6", formatted)
