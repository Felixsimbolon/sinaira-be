from django.conf import settings
from django.db import models

from inventory.models import Inventory


class SupplyRequest(models.Model):
	class Status(models.TextChoices):
		PENDING = "PENDING", "Pending"
		APPROVED = "APPROVED", "Approved"
		REJECTED = "REJECTED", "Rejected"

	item = models.ForeignKey(
		Inventory,
		on_delete=models.PROTECT,
		related_name="supply_requests",
	)
	quantity = models.PositiveIntegerField()
	reason = models.TextField()
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.PENDING,
	)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="created_supply_requests",
		limit_choices_to={"role": "THERAPIST"},
	)
	reviewed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="reviewed_supply_requests",
		limit_choices_to={"role": "SUPERVISOR"},
	)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"SR-{self.pk} {self.item.nama_barang} x {self.quantity} ({self.status})"


class InventoryStockHistory(models.Model):
	item = models.ForeignKey(
		Inventory,
		on_delete=models.PROTECT,
		related_name="stock_histories",
	)
	supply_request = models.ForeignKey(
		SupplyRequest,
		on_delete=models.PROTECT,
		related_name="stock_histories",
	)
	previous_stock = models.PositiveIntegerField()
	quantity_changed = models.IntegerField(
		help_text="Negative value indicates stock deduction.",
	)
	new_stock = models.PositiveIntegerField()
	changed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="inventory_stock_histories",
	)
	note = models.CharField(max_length=255, blank=True, default="")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return (
			f"Item {self.item_id}: {self.previous_stock} -> {self.new_stock} "
			f"(delta {self.quantity_changed})"
		)
