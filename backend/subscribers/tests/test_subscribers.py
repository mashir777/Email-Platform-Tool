import io
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from subscribers.models import ListMembership, Subscriber, SubscriberList


class SubscriberAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="SecurePass123!",
            username="other",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_create_list_and_subscriber(self):
        list_response = self.client.post(
            reverse("api:v1:subscribers:list-list"),
            {"name": "Newsletter", "description": "Main list"},
            format="json",
        )
        self.assertEqual(list_response.status_code, status.HTTP_201_CREATED)
        list_id = list_response.data["data"]["list"]["id"]

        sub_response = self.client.post(
            reverse("api:v1:subscribers:subscriber-list"),
            {
                "email": "john@gmail.com",
                "first_name": "John",
                "last_name": "Doe",
                "list_ids": [list_id],
            },
            format="json",
        )
        self.assertEqual(sub_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(sub_response.data["data"]["subscriber"]["email"], "john@gmail.com")

    def test_list_subscribers_filtered_by_list(self):
        subscriber_list = SubscriberList.objects.create(
            owner=self.user,
            name="VIP",
        )
        subscriber = Subscriber.objects.create(
            owner=self.user,
            email="vip@example.com",
        )
        subscriber.lists.add(subscriber_list)
        Subscriber.objects.create(owner=self.user, email="other@example.com")

        response = self.client.get(
            reverse("api:v1:subscribers:subscriber-list"),
            {"list_id": str(subscriber_list.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [s["email"] for s in response.data["data"]["subscribers"]]
        self.assertEqual(emails, ["vip@example.com"])

    def test_import_csv(self):
        csv_content = (
            "email,first_name,last_name\n"
            "import1@gmail.com,Ann,Ali\n"
            "fake@example.com,Bob,Bad\n"
        )
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "subscribers.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        import_data = response.data["data"]["import"]
        self.assertEqual(import_data["created"], 1)
        self.assertEqual(import_data["rejected"], 1)
        self.assertEqual(import_data["source_filename"], "subscribers.csv")
        self.assertEqual(import_data["list_name"], "subscribers")
        self.assertTrue(
            Subscriber.objects.filter(owner=self.user, email="import1@gmail.com").exists(),
        )
        imported = Subscriber.objects.get(owner=self.user, email="import1@gmail.com")
        self.assertEqual(imported.lists.filter(name="subscribers").count(), 1)
        self.assertEqual(
            SubscriberList.objects.get(owner=self.user, name="subscribers").source_filename,
            "subscribers.csv",
        )

    def test_import_csv_ignores_unrelated_selected_list(self):
        """Importing while another list is selected must not merge into that list."""
        other_list = SubscriberList.objects.create(
            owner=self.user,
            name="15-7-2026",
            source_filename="15-7-2026.csv",
        )
        csv_content = "email,first_name\nnewlead@gmail.com,Ada\n"
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "14-7-2026.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file, "list_id": str(other_list.id)},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        import_data = response.data["data"]["import"]
        self.assertEqual(import_data["list_name"], "14-7-2026")
        self.assertEqual(import_data["source_filename"], "14-7-2026.csv")

        imported = Subscriber.objects.get(owner=self.user, email="newlead@gmail.com")
        self.assertEqual(imported.lists.filter(name="14-7-2026").count(), 1)
        self.assertEqual(imported.lists.filter(id=other_list.id).count(), 0)

        other_list.refresh_from_db()
        self.assertEqual(other_list.source_filename, "15-7-2026.csv")
        self.assertEqual(other_list.name, "15-7-2026")

    def test_import_csv_reuses_matching_list_id(self):
        matching = SubscriberList.objects.create(
            owner=self.user,
            name="14-7-2026",
            source_filename="14-7-2026.csv",
        )
        csv_content = "email\nmatch@gmail.com\n"
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "14-7-2026.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file, "list_id": str(matching.id)},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        imported = Subscriber.objects.get(owner=self.user, email="match@gmail.com")
        self.assertEqual(imported.lists.filter(id=matching.id).count(), 1)
        self.assertEqual(response.data["data"]["import"]["list_id"], str(matching.id))

    def test_import_csv_with_list_column(self):
        csv_content = (
            "email,first_name,last_name,list\n"
            "csvlist@gmail.com,Sam,Ali,AshirShahzad\n"
        )
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "subscribers.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["import"]["created"], 1)
        self.assertEqual(response.data["data"]["import"]["lists_created"], 1)

        subscriber = Subscriber.objects.get(owner=self.user, email="csvlist@gmail.com")
        self.assertEqual(subscriber.lists.count(), 1)
        self.assertEqual(subscriber.lists.first().name, "AshirShahzad")

    def test_import_csv_company_columns(self):
        csv_content = (
            "email,name,Company,Industrial Company,Job Title,City\n"
            "lead@gmail.com,Sarah,Acme Logistics,logistics,Founder,Lahore\n"
        )
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "subscribers.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscriber = Subscriber.objects.get(owner=self.user, email="lead@gmail.com")
        self.assertEqual(subscriber.first_name, "Sarah")
        self.assertEqual(subscriber.company, "Acme Logistics")
        self.assertEqual(subscriber.industrial_company, "logistics")
        self.assertEqual(subscriber.custom_fields["Job Title"], "Founder")
        self.assertEqual(subscriber.custom_fields["City"], "Lahore")

    def test_import_csv_assigns_existing_subscriber_to_list_column(self):
        subscriber = Subscriber.objects.create(
            owner=self.user,
            email="existing@gmail.com",
            first_name="Old",
        )
        csv_content = "email,list\nexisting@gmail.com,Harry\n"
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "subscribers.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.lists.filter(name="Harry").count(), 1)

    def test_stats_endpoint(self):
        subscriber_list = SubscriberList.objects.create(
            owner=self.user,
            name="Stats list",
        )
        a = Subscriber.objects.create(owner=self.user, email="a@example.com")
        b = Subscriber.objects.create(
            owner=self.user,
            email="b@example.com",
            status=Subscriber.Status.UNSUBSCRIBED,
        )
        ListMembership.objects.create(list=subscriber_list, subscriber=a)
        ListMembership.objects.create(list=subscriber_list, subscriber=b)
        # Orphan (no list) must not inflate Total Emails
        Subscriber.objects.create(owner=self.user, email="orphan@example.com")

        response = self.client.get(reverse("api:v1:subscribers:stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["stats"]["total"], 2)
        self.assertEqual(response.data["data"]["stats"]["unsubscribed"], 1)
        self.assertEqual(response.data["data"]["stats"]["lists"], 1)

    def test_cannot_access_other_users_subscriber(self):
        subscriber = Subscriber.objects.create(
            owner=self.other_user,
            email="private@example.com",
        )
        response = self.client.get(
            reverse("api:v1:subscribers:subscriber-detail", args=[subscriber.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unverified_user_cannot_create(self):
        self.user.is_verified = False
        self.user.save()
        response = self.client.post(
            reverse("api:v1:subscribers:list-list"),
            {"name": "Blocked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("subscribers.reacher.verify_emails")
    def test_verify_list_with_reacher_in_place(self, mock_verify):
        mock_verify.return_value = {
            "good@gmail.com": {
                "is_reachable": "safe",
                "misc": {"is_disposable": False},
                "mx": {"accepts_mail": True},
                "smtp": {"is_deliverable": True, "is_disabled": False, "is_catch_all": False},
                "syntax": {"is_valid_syntax": True},
            },
            "fahad.munir@synqtech.net": {
                "is_reachable": "risky",
                "misc": {"is_disposable": False},
                "mx": {"accepts_mail": True},
                "smtp": {
                    "is_deliverable": True,
                    "is_disabled": False,
                    "is_catch_all": True,
                },
                "syntax": {"is_valid_syntax": True},
            },
            "spam@tempmail.com": {
                "is_reachable": "risky",
                "misc": {"is_disposable": True},
                "mx": {"accepts_mail": True},
                "smtp": {},
                "syntax": {"is_valid_syntax": True},
            },
            "bad@gmail.com": {
                "is_reachable": "invalid",
                "misc": {"is_disposable": False},
                "mx": {"accepts_mail": True},
                "smtp": {"is_deliverable": False, "is_disabled": False, "is_catch_all": False},
                "syntax": {"is_valid_syntax": True},
            },
        }
        subscriber_list = SubscriberList.objects.create(owner=self.user, name="Leads")
        for email in (
            "good@gmail.com",
            "fahad.munir@synqtech.net",
            "spam@tempmail.com",
            "bad@gmail.com",
        ):
            subscriber = Subscriber.objects.create(owner=self.user, email=email)
            subscriber.lists.add(subscriber_list)

        response = self.client.post(
            reverse("api:v1:subscribers:verify-list"),
            {"list_id": str(subscriber_list.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]["verify"]
        self.assertEqual(payload["total"], 4)
        self.assertEqual(payload["kept"], 3)
        self.assertEqual(payload["removed"], 1)
        self.assertEqual(subscriber_list.subscribers.count(), 3)
        self.assertTrue(
            Subscriber.objects.filter(owner=self.user, email="fahad.munir@synqtech.net").exists(),
        )
        self.assertTrue(
            Subscriber.objects.filter(owner=self.user, email="spam@tempmail.com").exists(),
        )
        self.assertFalse(
            Subscriber.objects.filter(owner=self.user, email="bad@gmail.com").exists(),
        )
        subscriber_list.refresh_from_db()
        self.assertTrue(subscriber_list.is_verified)

    @patch("subscribers.services.verify_list_with_reacher")
    @patch("subscribers.services.import_subscribers_from_csv")
    def test_filter_csv_imports_then_verifies(self, mock_import, mock_verify):
        mock_import.return_value = {
            "created": 2,
            "updated": 0,
            "skipped": 0,
            "rejected": 0,
            "list_id": "11111111-1111-1111-1111-111111111111",
            "list_name": "leads",
            "source_filename": "leads.csv",
        }
        mock_verify.return_value = {
            "list_id": "11111111-1111-1111-1111-111111111111",
            "list_name": "leads",
            "total": 2,
            "kept": 1,
            "removed": 1,
            "removed_breakdown": {"invalid": 1},
            "is_verified": True,
        }
        file = io.BytesIO(b"email\ngood@gmail.com\nbad@gmail.com\n")
        file.name = "leads.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:filter-csv"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]["filter"]
        self.assertEqual(payload["list_name"], "leads")
        self.assertEqual(payload["verify"]["kept"], 1)
        self.assertTrue(payload["is_verified"])
        mock_import.assert_called_once()
        mock_verify.assert_called_once()

    def test_csv_reimport_resets_send_status_to_waiting(self):
        from django.utils import timezone

        from campaigns.models import Campaign
        from sending.models import EmailQueueItem
        from subscribers.services import import_subscribers_from_csv

        subscriber_list = SubscriberList.objects.create(
            owner=self.user,
            name="16-7-2026",
            source_filename="16-7-2026.csv",
        )
        subscriber = Subscriber.objects.create(
            owner=self.user,
            email="minaammunir@gmail.com",
            status=Subscriber.Status.SUBSCRIBED,
        )
        subscriber.lists.add(subscriber_list)
        campaign = Campaign.objects.create(
            owner=self.user,
            name="Test",
            subject="Hi",
            html_content="<p>Hi</p>",
            subscriber_list=subscriber_list,
        )

        EmailQueueItem.objects.create(
            owner=self.user,
            campaign=campaign,
            subscriber=subscriber,
            to_email=subscriber.email,
            status=EmailQueueItem.Status.SENT,
            sent_at=timezone.now(),
        )

        response = self.client.get(
            reverse("api:v1:subscribers:subscriber-list"),
            {"list_id": str(subscriber_list.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["subscribers"][0]["send_status"],
            "sent",
        )

        csv_content = "email\nminaammunir@gmail.com\n"
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "16-7-2026.csv"
        import_subscribers_from_csv(
            owner=self.user,
            csv_file=csv_file,
            list_id=str(subscriber_list.id),
        )

        response = self.client.get(
            reverse("api:v1:subscribers:subscriber-list"),
            {"list_id": str(subscriber_list.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["data"]["subscribers"][0]["send_status"],
            "waiting",
        )

        list_response = self.client.get(reverse("api:v1:subscribers:list-list"))
        lists = list_response.data["data"]["lists"]
        matched = next(item for item in lists if item["id"] == str(subscriber_list.id))
        self.assertEqual(matched["waiting_emails"], 1)
        self.assertEqual(matched["sent_emails"], 0)
