from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Inventory

from .models import InventoryStockHistory, SupplyRequest


class SupplyRequestAPITestCase(APITestCase):
	endpoint = "/api/supply-request"
	items_endpoint = "/api/supply-request/items"
	my_requests_endpoint = "/api/supply-request/me"

	def setUp(self):
		self.user_model = get_user_model()
		self.therapist = self._create_user("therapist01", "THERAPIST")
		self.supervisor = self._create_user("supervisor01", "SUPERVISOR")
		self.owner = self._create_user("owner01", "OWNER")

		self.active_item = Inventory.objects.create(
			nama_barang="Minyak Relax",
			kategori=Inventory.Kategori.BAHAN_BODY_MASSAGE,
			lokasi=Inventory.Lokasi.CILEGON,
			jumlah_stok=20,
			threshold_minimum=3,
			keterangan="",
			is_deleted=False,
		)
		self.inactive_item = Inventory.objects.create(
			nama_barang="Masker Lama",
			kategori=Inventory.Kategori.BAHAN_MASKER,
			lokasi=Inventory.Lokasi.SERANG,
			jumlah_stok=10,
			threshold_minimum=2,
			keterangan="",
			is_deleted=True,
		)

	def _create_user(self, username: str, role: str):
		return self.user_model.objects.create_user(
			username=username,
			password="Password123!",
			email=f"{username}@example.com",
			name=username,
			role=role,
		)

	def _detail_endpoint(self, request_id: int) -> str:
		return f"/api/supply-request/{request_id}"

	def test_create_supply_request_success_for_therapist(self):
		self.client.force_authenticate(user=self.therapist)

		response = self.client.post(
			self.endpoint,
			{
				"itemId": self.active_item.id,
				"quantity": 3,
				"reason": "Stok habis untuk treatment sore.",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["status"], SupplyRequest.Status.PENDING)
		self.assertEqual(response.data["itemName"], self.active_item.nama_barang)
		self.assertEqual(SupplyRequest.objects.count(), 1)

	def test_create_supply_request_forbidden_for_non_therapist(self):
		self.client.force_authenticate(user=self.supervisor)

		response = self.client.post(
			self.endpoint,
			{
				"itemId": self.active_item.id,
				"quantity": 2,
				"reason": "Need stock",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_create_supply_request_rejects_invalid_quantity(self):
		self.client.force_authenticate(user=self.therapist)

		response = self.client.post(
			self.endpoint,
			{
				"itemId": self.active_item.id,
				"quantity": 0,
				"reason": "Need stock",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_create_supply_request_rejects_unknown_or_inactive_item(self):
		self.client.force_authenticate(user=self.therapist)

		response_unknown = self.client.post(
			self.endpoint,
			{
				"itemId": 999999,
				"quantity": 1,
				"reason": "Need stock",
			},
			format="json",
		)
		self.assertEqual(response_unknown.status_code, status.HTTP_404_NOT_FOUND)

		response_inactive = self.client.post(
			self.endpoint,
			{
				"itemId": self.inactive_item.id,
				"quantity": 1,
				"reason": "Need stock",
			},
			format="json",
		)
		self.assertEqual(response_inactive.status_code, status.HTTP_404_NOT_FOUND)

	def test_read_supply_request_list_supervisor_success(self):
		SupplyRequest.objects.create(
			item=self.active_item,
			quantity=2,
			reason="Kebutuhan sesi pagi",
			created_by=self.therapist,
		)

		self.client.force_authenticate(user=self.supervisor)
		response = self.client.get(self.endpoint)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(
			set(response.data[0].keys()),
			{"id", "itemId", "itemName", "quantity", "reason", "status", "createdBy", "createdAt"},
		)

	def test_read_supply_request_list_empty_returns_200_and_empty_array(self):
		self.client.force_authenticate(user=self.supervisor)
		response = self.client.get(self.endpoint)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data, [])

	def test_read_supply_request_list_forbidden_for_non_supervisor(self):
		self.client.force_authenticate(user=self.owner)
		response = self.client.get(self.endpoint)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_get_supply_request_items_for_therapist(self):
		self.client.force_authenticate(user=self.therapist)
		response = self.client.get(self.items_endpoint)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["id"], self.active_item.id)
		self.assertEqual(response.data[0]["name"], self.active_item.nama_barang)

	def test_get_supply_request_items_forbidden_for_non_therapist(self):
		self.client.force_authenticate(user=self.supervisor)
		response = self.client.get(self.items_endpoint)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_get_my_supply_requests_returns_only_current_therapist_rows(self):
		other_therapist = self._create_user("therapist02", "THERAPIST")
		SupplyRequest.objects.create(
			item=self.active_item,
			quantity=2,
			reason="Req 1",
			created_by=self.therapist,
		)
		SupplyRequest.objects.create(
			item=self.active_item,
			quantity=3,
			reason="Req 2",
			created_by=other_therapist,
		)

		self.client.force_authenticate(user=self.therapist)
		response = self.client.get(self.my_requests_endpoint)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["quantity"], 2)

	def test_get_my_supply_requests_forbidden_for_non_therapist(self):
		self.client.force_authenticate(user=self.supervisor)
		response = self.client.get(self.my_requests_endpoint)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_get_supply_request_detail_for_supervisor(self):
		req = SupplyRequest.objects.create(
			item=self.active_item,
			quantity=1,
			reason="Need more",
			created_by=self.therapist,
		)

		self.client.force_authenticate(user=self.supervisor)
		response = self.client.get(self._detail_endpoint(req.id))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["id"], req.id)
		self.assertEqual(response.data["itemName"], self.active_item.nama_barang)

	def test_get_supply_request_detail_not_found(self):
		self.client.force_authenticate(user=self.supervisor)
		response = self.client.get(self._detail_endpoint(123456))

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_patch_supply_request_approve_success_updates_stock_and_history(self):
		req = SupplyRequest.objects.create(
			item=self.active_item,
			quantity=4,
			reason="Kebutuhan sesi malam",
			created_by=self.therapist,
		)

		self.client.force_authenticate(user=self.supervisor)
		response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": SupplyRequest.Status.APPROVED},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)

		req.refresh_from_db()
		self.active_item.refresh_from_db()

		self.assertEqual(req.status, SupplyRequest.Status.APPROVED)
		self.assertEqual(self.active_item.jumlah_stok, 16)
		self.assertEqual(InventoryStockHistory.objects.filter(supply_request=req).count(), 1)

		history = InventoryStockHistory.objects.get(supply_request=req)
		self.assertEqual(history.previous_stock, 20)
		self.assertEqual(history.new_stock, 16)
		self.assertEqual(history.quantity_changed, -4)

	def test_patch_supply_request_approve_rejects_when_stock_insufficient(self):
		self.active_item.jumlah_stok = 2
		self.active_item.save(update_fields=["jumlah_stok", "updated_at"])

		req = SupplyRequest.objects.create(
			item=self.active_item,
			quantity=5,
			reason="Need more",
			created_by=self.therapist,
		)

		self.client.force_authenticate(user=self.supervisor)
		response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": SupplyRequest.Status.APPROVED},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

		req.refresh_from_db()
		self.active_item.refresh_from_db()
		self.assertEqual(req.status, SupplyRequest.Status.PENDING)
		self.assertEqual(self.active_item.jumlah_stok, 2)
		self.assertEqual(InventoryStockHistory.objects.filter(supply_request=req).count(), 0)

	def test_patch_supply_request_reject_success_without_stock_change(self):
		req = SupplyRequest.objects.create(
			item=self.active_item,
			quantity=3,
			reason="Need more",
			created_by=self.therapist,
		)

		self.client.force_authenticate(user=self.supervisor)
		response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": SupplyRequest.Status.REJECTED},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)

		req.refresh_from_db()
		self.active_item.refresh_from_db()
		self.assertEqual(req.status, SupplyRequest.Status.REJECTED)
		self.assertEqual(self.active_item.jumlah_stok, 20)
		self.assertEqual(InventoryStockHistory.objects.filter(supply_request=req).count(), 0)

	def test_patch_supply_request_requires_pending_status(self):
		req = SupplyRequest.objects.create(
			item=self.active_item,
			quantity=1,
			reason="Need more",
			created_by=self.therapist,
			status=SupplyRequest.Status.REJECTED,
		)

		self.client.force_authenticate(user=self.supervisor)
		response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": SupplyRequest.Status.APPROVED},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_patch_supply_request_validates_payload_and_permissions(self):
		req = SupplyRequest.objects.create(
			item=self.active_item,
			quantity=1,
			reason="Need more",
			created_by=self.therapist,
		)

		self.client.force_authenticate(user=self.therapist)
		forbidden_response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": SupplyRequest.Status.APPROVED},
			format="json",
		)
		self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(user=self.supervisor)
		invalid_status_response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": "PENDING"},
			format="json",
		)
		self.assertEqual(invalid_status_response.status_code, status.HTTP_400_BAD_REQUEST)

		extra_field_response = self.client.patch(
			self._detail_endpoint(req.id),
			{"status": SupplyRequest.Status.REJECTED, "reason": "nope"},
			format="json",
		)
		self.assertEqual(extra_field_response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_patch_supply_request_not_found(self):
		self.client.force_authenticate(user=self.supervisor)
		response = self.client.patch(
			self._detail_endpoint(999999),
			{"status": SupplyRequest.Status.APPROVED},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
