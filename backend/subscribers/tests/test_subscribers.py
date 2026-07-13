import io

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from subscribers.models import Subscriber, SubscriberList


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
        subscriber_list = SubscriberList.objects.create(owner=self.user, name="Import")
        csv_content = (
            "email,first_name,last_name\n"
            "import1@gmail.com,Ann,Ali\n"
            "fake@example.com,Bob,Bad\n"
        )
        file = io.BytesIO(csv_content.encode("utf-8"))
        file.name = "subscribers.csv"

        response = self.client.post(
            reverse("api:v1:subscribers:import"),
            {"file": file, "list_id": str(subscriber_list.id)},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["import"]["created"], 1)
        self.assertEqual(response.data["data"]["import"]["rejected"], 1)
        self.assertTrue(
            Subscriber.objects.filter(owner=self.user, email="import1@gmail.com").exists(),
        )
        imported = Subscriber.objects.get(owner=self.user, email="import1@gmail.com")
        self.assertEqual(imported.lists.filter(name="Import").count(), 1)

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
        Subscriber.objects.create(owner=self.user, email="a@example.com")
        Subscriber.objects.create(
            owner=self.user,
            email="b@example.com",
            status=Subscriber.Status.UNSUBSCRIBED,
        )

        response = self.client.get(reverse("api:v1:subscribers:stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["stats"]["total"], 2)
        self.assertEqual(response.data["data"]["stats"]["unsubscribed"], 1)

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
