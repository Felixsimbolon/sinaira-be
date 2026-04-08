from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from event.models import Promo


class PromoAdminApiTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner_promo",
			email="owner_promo@example.com",
			password="password123",
			name="Owner Promo",
			role=User.Role.OWNER,
		)
		self.admin = User.objects.create_user(
			username="admin_promo",
			email="admin_promo@example.com",
			password="password123",
			name="Admin Promo",
			role=User.Role.ADMIN,
		)

	def test_owner_can_create_promo(self):
		self.client.force_authenticate(user=self.owner)
		payload = {
			"title": "Spa Weekend Offer",
			"description": "Get exclusive spa access",
			"content_type": "promo",
			"posting_state": "published",
			"start_date": str(timezone.localdate() - timedelta(days=1)),
			"end_date": str(timezone.localdate() + timedelta(days=1)),
		}

		response = self.client.post("/api/admin/promos", payload, format="json")

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["title"], "Spa Weekend Offer")
		self.assertEqual(response.data["computed_status"], "active")
		self.assertTrue(response.data["cta_enabled"])

	def test_non_owner_forbidden_to_access_admin_endpoint(self):
		self.client.force_authenticate(user=self.admin)

		response = self.client.get("/api/admin/promos", format="json")

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_admin_list_empty_message(self):
		self.client.force_authenticate(user=self.owner)

		response = self.client.get("/api/admin/promos", format="json")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["message"], "Data promo tidak tersedia")
		self.assertEqual(response.data["results"], [])

	def test_validate_end_date_must_be_after_start_date(self):
		self.client.force_authenticate(user=self.owner)
		payload = {
			"title": "Invalid Date",
			"description": "Desc",
			"start_date": str(timezone.localdate() + timedelta(days=5)),
			"end_date": str(timezone.localdate() + timedelta(days=2)),
		}

		response = self.client.post("/api/admin/promos", payload, format="json")

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("end_date", response.data)


class PromoPublicApiTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner_public",
			email="owner_public@example.com",
			password="password123",
			name="Owner Public",
			role=User.Role.OWNER,
		)
		today = timezone.localdate()

		self.active_promo = Promo.objects.create(
			title="Active Promo",
			description="Promo aktif",
			content_type=Promo.ContentType.PROMO,
			posting_state=Promo.PostingState.PUBLISHED,
			start_date=today - timedelta(days=2),
			end_date=today + timedelta(days=2),
			created_by=self.owner,
			updated_by=self.owner,
		)
		self.expired_event = Promo.objects.create(
			title="Expired Event",
			description="Event sudah lewat",
			content_type=Promo.ContentType.EVENT,
			posting_state=Promo.PostingState.PUBLISHED,
			start_date=today - timedelta(days=7),
			end_date=today - timedelta(days=1),
			created_by=self.owner,
			updated_by=self.owner,
		)
		Promo.objects.create(
			title="Draft Promo",
			description="Draft",
			posting_state=Promo.PostingState.DRAFT,
			created_by=self.owner,
			updated_by=self.owner,
		)
		Promo.objects.create(
			title="Archived Promo",
			description="Archived",
			posting_state=Promo.PostingState.ARCHIVED,
			created_by=self.owner,
			updated_by=self.owner,
		)
		self.deleted_promo = Promo.objects.create(
			title="Deleted Promo",
			description="Deleted",
			posting_state=Promo.PostingState.PUBLISHED,
			created_by=self.owner,
			updated_by=self.owner,
		)
		self.deleted_promo.soft_delete()

	def test_public_list_only_shows_published_and_not_deleted(self):
		response = self.client.get("/api/promos", format="json")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		returned_titles = {item["title"] for item in response.data["results"]}
		self.assertIn("Active Promo", returned_titles)
		self.assertIn("Expired Event", returned_titles)
		self.assertNotIn("Draft Promo", returned_titles)
		self.assertNotIn("Archived Promo", returned_titles)
		self.assertNotIn("Deleted Promo", returned_titles)

	def test_expired_post_still_visible_but_cta_disabled(self):
		response = self.client.get(f"/api/promos/{self.expired_event.id}", format="json")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["computed_status"], "expired")
		self.assertFalse(response.data["cta_enabled"])
		self.assertEqual(response.data["availability_status"], "closed")

	def test_active_post_has_enabled_cta(self):
		response = self.client.get(f"/api/promos/{self.active_promo.id}", format="json")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["computed_status"], "active")
		self.assertTrue(response.data["cta_enabled"])
		self.assertEqual(response.data["availability_status"], "available")


class PromoAdminWorkflowTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner_workflow",
			email="owner_workflow@example.com",
			password="password123",
			name="Owner Workflow",
			role=User.Role.OWNER,
		)
		self.promo = Promo.objects.create(
			title="Workflow Promo",
			description="Workflow",
			posting_state=Promo.PostingState.PUBLISHED,
			created_by=self.owner,
			updated_by=self.owner,
		)
		self.client.force_authenticate(user=self.owner)

	def test_archive_and_unarchive(self):
		archive_resp = self.client.patch(f"/api/admin/promos/{self.promo.id}/archive", {}, format="json")
		self.assertEqual(archive_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(archive_resp.data["posting_state"], "archived")

		unarchive_resp = self.client.patch(f"/api/admin/promos/{self.promo.id}/unarchive", {}, format="json")
		self.assertEqual(unarchive_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(unarchive_resp.data["posting_state"], "draft")

	def test_delete_is_soft_delete(self):
		delete_resp = self.client.delete(f"/api/admin/promos/{self.promo.id}")
		self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

		self.promo.refresh_from_db()
		self.assertIsNotNone(self.promo.deleted_at)

		public_resp = self.client.get(f"/api/promos/{self.promo.id}", format="json")
		self.assertEqual(public_resp.status_code, status.HTTP_404_NOT_FOUND)
