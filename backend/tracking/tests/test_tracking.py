from django.test import Client, TestCase, override_settings
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


@override_settings(
    TRACKING_PUBLIC_BASE_URL="https://mail.example.com",
    TRACKING_REQUIRE_SAME_DOMAIN=False,
    TRACKING_FORCE_REMOTE_PIXEL=True,
    TRACKING_PROXY_BASE_URL="",
)
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
            from_email="info@example.com",
        )
        self.assertIn("/t/o/", html)
        self.assertIn("<img", html.lower())
        self.assertNotIn("Confirm you received this email", html)

    def test_inject_plain_text_campaign_gets_pixel(self):
        html = inject_open_tracking_pixel(
            "Hi there\n\nPlain text campaign body",
            str(self.queue_item.id),
            campaign_id=str(self.campaign.id),
            from_email="info@example.com",
        )
        self.assertIn("/t/o/", html)
        self.assertIn("<img", html.lower())
        self.assertNotIn("Confirm you received this email", html)

    @override_settings(
        TRACKING_PUBLIC_BASE_URL="https://datrixworld.com",
        TRACKING_ORIGIN_BACKEND_URL="https://passport.trycloudflare.com",
        TRACKING_REQUIRE_SAME_DOMAIN=True,
        TRACKING_FORCE_REMOTE_PIXEL=False,
    )
    def test_falls_back_to_tunnel_when_proxy_offline(self):
        from unittest.mock import patch

        with patch(
            "tracking.services._same_domain_proxy_is_live",
            return_value=False,
        ), patch(
            "tracking.services._origin_backend_reachable",
            return_value=True,
        ), patch(
            "tracking.services.get_live_origin_backend_url",
            return_value="https://passport.trycloudflare.com",
        ):
            html = inject_open_tracking_pixel(
                self.campaign.html_content,
                str(self.queue_item.id),
                campaign_id=str(self.campaign.id),
                from_email="info@datrixworld.com",
            )
        self.assertIn("trycloudflare.com", html)
        self.assertIn("/t/o/", html)

    @override_settings(
        TRACKING_PUBLIC_BASE_URL="https://datrixworld.com",
        TRACKING_ORIGIN_BACKEND_URL="https://passport.trycloudflare.com",
        TRACKING_REQUIRE_SAME_DOMAIN=True,
        TRACKING_FORCE_REMOTE_PIXEL=False,
    )
    def test_same_domain_when_proxy_live(self):
        from unittest.mock import patch

        with patch(
            "tracking.services._same_domain_proxy_is_live",
            return_value=True,
        ):
            html = inject_open_tracking_pixel(
                self.campaign.html_content,
                str(self.queue_item.id),
                campaign_id=str(self.campaign.id),
                from_email="info@datrixworld.com",
            )
        self.assertIn("https://datrixworld.com/t/o/", html)
        self.assertNotIn("trycloudflare.com", html)

    @override_settings(
        TRACKING_PROXY_BASE_URL="https://datrixworld.com",
        TRACKING_PROXY_SECRET="test-secret",
    )
    def test_same_domain_proxy_pixel_and_decode(self):
        from unittest.mock import patch
        from tracking.services import _queue_item_id_from_tracking_path

        with patch(
            "tracking.services._same_domain_proxy_is_live",
            return_value=True,
        ):
            html = inject_open_tracking_pixel(
                self.campaign.html_content,
                str(self.queue_item.id),
                campaign_id=str(self.campaign.id),
                from_email="info@datrixworld.com",
            )
        # Same-domain, tunnel-free pixel; links are left untouched.
        self.assertIn("https://datrixworld.com/t/open.php?path=", html)
        self.assertNotIn("/t/c/", html)
        self.assertNotIn("trycloudflare.com", html)

        import re
        import urllib.parse

        match = re.search(r"open\.php\?path=([^\"&]+)", html)
        self.assertIsNotNone(match)
        path = urllib.parse.unquote(match.group(1))
        self.assertEqual(
            _queue_item_id_from_tracking_path(path),
            str(self.queue_item.id),
        )

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
