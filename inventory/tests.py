from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from inventory.models import Inventory, TherapistSupplyAssignment
from therapist.models import Therapist


class TherapistSupplyAssignmentAuthTest(APITestCase):
    """Test authentication – 401 for unauthenticated requests."""

    def setUp(self):
        self.url = "/api/therapist-supply-assignments/"

    def test_list_no_auth_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_no_auth_returns_401(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_no_auth_returns_401(self):
        response = self.client.patch(f"{self.url}999/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_no_auth_returns_401(self):
        response = self.client.delete(f"{self.url}999/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TherapistSupplyAssignmentPermissionTest(APITestCase):
    """Test role permissions – 403 for ADMIN and THERAPIST roles."""

    def setUp(self):
        self.url = "/api/therapist-supply-assignments/"
        self.admin_user = User.objects.create_user(
            username="perm_admin",
            email="perm_admin@example.com",
            password="password123",
            name="Perm Admin",
            role=User.Role.ADMIN,
        )
        self.therapist_user = User.objects.create_user(
            username="perm_therapist",
            email="perm_therapist@example.com",
            password="password123",
            name="Perm Therapist",
            role=User.Role.THERAPIST,
        )

    def test_admin_role_returns_403(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_therapist_role_returns_403(self):
        self.client.force_authenticate(user=self.therapist_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_create_returns_403(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_therapist_delete_returns_403(self):
        self.client.force_authenticate(user=self.therapist_user)
        response = self.client.delete(f"{self.url}1/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TherapistSupplyAssignmentCRUDTest(APITestCase):
    """Test create, read, update, delete for assignments."""

    def setUp(self):
        self.url = "/api/therapist-supply-assignments/"

        # OWNER user
        self.owner = User.objects.create_user(
            username="assign_owner",
            email="assign_owner@example.com",
            password="password123",
            name="Assign Owner",
            role=User.Role.OWNER,
        )

        # SUPERVISOR user
        self.supervisor = User.objects.create_user(
            username="assign_supervisor",
            email="assign_supervisor@example.com",
            password="password123",
            name="Assign Supervisor",
            role=User.Role.SUPERVISOR,
        )

        # Therapist profile
        self.therapist = Therapist.objects.create(
            username="assign_therapist_profile",
            name="Therapist Profile",
            email="assign_therapist_profile@example.com",
        )

        # Another therapist
        self.therapist2 = Therapist.objects.create(
            username="assign_therapist_profile2",
            name="Therapist Profile 2",
            email="assign_therapist_profile2@example.com",
        )

        # Inventory item with usage_per_unit = 5
        self.item = Inventory.objects.create(
            nama_barang="Minyak Pijat",
            kategori=Inventory.Kategori.BAHAN_BODY_MASSAGE,
            lokasi=Inventory.Lokasi.CILEGON,
            jumlah_stok=100,
            threshold_minimum=10,
            usage_per_unit=5,
        )

        # Another item
        self.item2 = Inventory.objects.create(
            nama_barang="Masker Wajah",
            kategori=Inventory.Kategori.BAHAN_MASKER,
            lokasi=Inventory.Lokasi.SERANG,
            jumlah_stok=50,
            threshold_minimum=5,
            usage_per_unit=3,
        )

    # ── CREATE TESTS ──────────────────────────────────────────────────

    def test_create_assignment_valid_owner(self):
        """Owner can create a valid assignment."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 10,
            "notes": "Batch pertama",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data["item_id"], self.item.pk)
        self.assertEqual(data["therapist_id"], self.therapist.pk)
        self.assertEqual(data["quantity_assigned"], 10)
        self.assertEqual(data["usage_per_unit"], 5)
        self.assertEqual(data["total_usage"], 50)  # 10 * 5
        self.assertEqual(data["remaining_usage"], 50)
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(data["notes"], "Batch pertama")
        self.assertEqual(data["assigned_by"], self.owner.pk)

    def test_create_assignment_valid_supervisor(self):
        """Supervisor can also create a valid assignment."""
        self.client.force_authenticate(user=self.supervisor)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_assignment_deducts_stock(self):
        """Creating assignment should deduct item stock."""
        self.client.force_authenticate(user=self.owner)
        initial_stock = self.item.jumlah_stok  # 100

        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 15,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, initial_stock - 15)

    def test_create_assignment_invalid_quantity_zero(self):
        """quantityAssigned = 0 should return 400."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 0,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity_assigned", response.data)

    def test_create_assignment_invalid_quantity_negative(self):
        """quantityAssigned < 0 should return 400."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": -5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_assignment_exceeds_stock(self):
        """quantityAssigned > jumlah_stok should return 400."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 999,  # stok hanya 100
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_assignment_deleted_item_returns_400(self):
        """Soft-deleted item should not be assignable."""
        self.item.is_deleted = True
        self.item.save()
        self.client.force_authenticate(user=self.owner)

        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_assignment_invalid_item_returns_400(self):
        """Non-existent item should return 400."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": 99999,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_assignment_invalid_therapist_returns_400(self):
        """Non-existent therapist should return 400."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": 99999,
            "quantity_assigned": 5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_assignment_inactive_therapist_returns_400(self):
        """Inactive therapist should return 400."""
        self.therapist.is_active = False
        self.therapist.save()
        self.client.force_authenticate(user=self.owner)

        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── MULTI-ASSIGNMENT TEST ─────────────────────────────────────────

    def test_multi_assignment_same_therapist_same_item(self):
        """One therapist can have multiple assignments for the same item."""
        self.client.force_authenticate(user=self.owner)

        payload1 = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 10,
            "notes": "Batch 1",
        }
        resp1 = self.client.post(self.url, payload1, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        payload2 = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 5,
            "notes": "Batch 2",
        }
        resp2 = self.client.post(self.url, payload2, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)

        # Verify both exist
        assignments = TherapistSupplyAssignment.objects.filter(
            item=self.item,
            therapist=self.therapist,
            is_deleted=False,
        )
        self.assertEqual(assignments.count(), 2)

        # Verify stock was deducted twice
        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, 100 - 10 - 5)

    # ── CALCULATION TESTS ─────────────────────────────────────────────

    def test_total_usage_calculation(self):
        """totalUsage = quantityAssigned * usagePerUnit."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 7,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_usage"], 7 * 5)  # 35
        self.assertEqual(response.data["remaining_usage"], 35)

    def test_usage_per_unit_snapshot(self):
        """usagePerUnit on assignment should be a snapshot from inventory."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 3,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment_id = response.data["id"]

        # Change inventory usage_per_unit
        self.item.usage_per_unit = 10
        self.item.save()

        # Existing assignment should keep old snapshot
        assignment = TherapistSupplyAssignment.objects.get(pk=assignment_id)
        self.assertEqual(assignment.usage_per_unit, 5)  # original value
        self.assertEqual(assignment.total_usage, 15)  # 3 * 5

    def test_remaining_usage_equals_total_at_creation(self):
        """remainingUsage should equal totalUsage at creation."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "item_id": self.item2.pk,
            "therapist_id": self.therapist.pk,
            "quantity_assigned": 4,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_usage"], 4 * 3)  # 12
        self.assertEqual(response.data["remaining_usage"], 12)

    # ── LIST TESTS ────────────────────────────────────────────────────

    def test_list_assignments(self):
        """List should return only non-deleted assignments."""
        self.client.force_authenticate(user=self.owner)

        # Create 2 assignments
        for i in range(2):
            self.client.post(
                self.url,
                {
                    "item_id": self.item.pk,
                    "therapist_id": self.therapist.pk,
                    "quantity_assigned": 5,
                },
                format="json",
            )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_with_filter(self):
        """List should support filtering by therapist_id."""
        self.client.force_authenticate(user=self.owner)

        self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 5,
            },
            format="json",
        )
        self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist2.pk,
                "quantity_assigned": 5,
            },
            format="json",
        )

        resp = self.client.get(self.url, {"therapist_id": self.therapist.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["therapist_id"], self.therapist.pk)

    def test_list_empty_returns_200(self):
        """List with no data should return 200 with empty array."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    # ── UPDATE TESTS ──────────────────────────────────────────────────

    def test_update_quantity(self):
        """PATCH should update quantity and recalculate totalUsage/remainingUsage."""
        self.client.force_authenticate(user=self.owner)

        # Create
        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 10,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        assignment_id = resp.data["id"]

        # Original: total_usage=50, remaining_usage=50

        # Update quantity to 15
        resp_patch = self.client.patch(
            f"{self.url}{assignment_id}/",
            {"quantity_assigned": 15},
            format="json",
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_patch.data["quantity_assigned"], 15)
        self.assertEqual(resp_patch.data["total_usage"], 75)  # 15 * 5
        self.assertEqual(resp_patch.data["remaining_usage"], 75)  # 50 + (75-50) = 75

    def test_update_quantity_adjusts_stock(self):
        """Updating quantity should adjust stock correctly."""
        self.client.force_authenticate(user=self.owner)

        # Create with qty=10, stock goes from 100 to 90
        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 10,
            },
            format="json",
        )
        assignment_id = resp.data["id"]
        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, 90)

        # Update qty to 15 — should deduct 5 more → 85
        self.client.patch(
            f"{self.url}{assignment_id}/",
            {"quantity_assigned": 15},
            format="json",
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, 85)

        # Update qty to 8 — should return 7 → 92
        self.client.patch(
            f"{self.url}{assignment_id}/",
            {"quantity_assigned": 8},
            format="json",
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, 92)

    def test_update_notes_only(self):
        """PATCH notes should not change quantity/usage."""
        self.client.force_authenticate(user=self.owner)

        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 5,
                "notes": "Original",
            },
            format="json",
        )
        assignment_id = resp.data["id"]

        resp_patch = self.client.patch(
            f"{self.url}{assignment_id}/",
            {"notes": "Updated notes"},
            format="json",
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_patch.data["notes"], "Updated notes")
        self.assertEqual(resp_patch.data["quantity_assigned"], 5)

    def test_update_records_updated_by(self):
        """PATCH should record updated_by for audit."""
        self.client.force_authenticate(user=self.owner)

        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 5,
            },
            format="json",
        )
        assignment_id = resp.data["id"]

        # Switch to supervisor and update
        self.client.force_authenticate(user=self.supervisor)
        self.client.patch(
            f"{self.url}{assignment_id}/",
            {"notes": "supervisor updated"},
            format="json",
        )

        assignment = TherapistSupplyAssignment.objects.get(pk=assignment_id)
        self.assertEqual(assignment.updated_by, self.supervisor)

    def test_update_nonexistent_returns_404(self):
        """PATCH non-existent assignment returns 404."""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.patch(
            f"{self.url}99999/",
            {"quantity_assigned": 5},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_invalid_quantity_returns_400(self):
        """PATCH with quantity=0 returns 400."""
        self.client.force_authenticate(user=self.owner)

        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 5,
            },
            format="json",
        )
        assignment_id = resp.data["id"]

        resp_patch = self.client.patch(
            f"{self.url}{assignment_id}/",
            {"quantity_assigned": 0},
            format="json",
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_400_BAD_REQUEST)

    # ── DELETE (SOFT DELETE) TESTS ────────────────────────────────────

    def test_soft_delete_assignment(self):
        """DELETE should soft-delete and return stock."""
        self.client.force_authenticate(user=self.owner)

        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 20,
            },
            format="json",
        )
        assignment_id = resp.data["id"]
        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, 80)

        # Delete
        resp_del = self.client.delete(f"{self.url}{assignment_id}/")
        self.assertEqual(resp_del.status_code, status.HTTP_200_OK)

        # Verify soft delete
        assignment = TherapistSupplyAssignment.objects.get(pk=assignment_id)
        self.assertTrue(assignment.is_deleted)
        self.assertEqual(assignment.status, "INACTIVE")
        self.assertIsNotNone(assignment.deleted_at)
        self.assertEqual(assignment.deleted_by, self.owner)

        # Stock restored
        self.item.refresh_from_db()
        self.assertEqual(self.item.jumlah_stok, 100)

    def test_soft_delete_not_in_list(self):
        """Soft-deleted assignments should not appear in list."""
        self.client.force_authenticate(user=self.owner)

        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 5,
            },
            format="json",
        )
        assignment_id = resp.data["id"]

        self.client.delete(f"{self.url}{assignment_id}/")

        resp_list = self.client.get(self.url)
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_list.data), 0)

    def test_delete_nonexistent_returns_404(self):
        """DELETE non-existent assignment returns 404."""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.delete(f"{self.url}99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_already_deleted_returns_404(self):
        """DELETE an already-deleted assignment returns 404."""
        self.client.force_authenticate(user=self.owner)

        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 5,
            },
            format="json",
        )
        assignment_id = resp.data["id"]

        self.client.delete(f"{self.url}{assignment_id}/")
        resp2 = self.client.delete(f"{self.url}{assignment_id}/")
        self.assertEqual(resp2.status_code, status.HTTP_404_NOT_FOUND)

    # ── AUDIT TRAIL TESTS ─────────────────────────────────────────────

    def test_assigned_by_recorded(self):
        """Assignment should record who created it."""
        self.client.force_authenticate(user=self.supervisor)
        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 3,
            },
            format="json",
        )
        self.assertEqual(resp.data["assigned_by"], self.supervisor.pk)

    def test_assigned_at_recorded(self):
        """Assignment should record when it was created."""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(
            self.url,
            {
                "item_id": self.item.pk,
                "therapist_id": self.therapist.pk,
                "quantity_assigned": 3,
            },
            format="json",
        )
        self.assertIsNotNone(resp.data["assigned_at"])
