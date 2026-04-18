from django.contrib import admin

from .models import InventoryStockHistory, SupplyRequest


@admin.register(SupplyRequest)
class SupplyRequestAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"item",
		"quantity",
		"status",
		"created_by",
		"reviewed_by",
		"created_at",
	)
	list_filter = ("status", "created_at")
	search_fields = ("item__nama_barang", "created_by__username", "created_by__name")


@admin.register(InventoryStockHistory)
class InventoryStockHistoryAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"item",
		"supply_request",
		"previous_stock",
		"quantity_changed",
		"new_stock",
		"changed_by",
		"created_at",
	)
	list_filter = ("created_at",)
	search_fields = ("item__nama_barang", "supply_request__id", "changed_by__username")
