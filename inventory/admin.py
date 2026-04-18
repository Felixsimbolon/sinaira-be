from django.contrib import admin

from .models import Inventory, SupplyUsageLog, TherapistSupplyAssignment


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "nama_barang",
        "kategori",
        "lokasi",
        "jumlah_stok",
        "threshold_minimum",
        "usage_per_unit",
        "is_deleted",
        "updated_at",
    )
    list_filter = ("is_deleted", "kategori", "lokasi")
    search_fields = ("nama_barang", "kategori", "keterangan")


@admin.register(TherapistSupplyAssignment)
class TherapistSupplyAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "therapist",
        "quantity_assigned",
        "usage_per_unit",
        "total_usage",
        "remaining_usage",
        "status",
        "assigned_at",
        "is_deleted",
    )
    list_filter = ("status", "is_deleted")
    search_fields = ("item__nama_barang", "therapist__name")
    raw_id_fields = ("item", "therapist", "assigned_by", "updated_by", "deleted_by")


@admin.register(SupplyUsageLog)
class SupplyUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "therapist",
        "jumlah",
        "tanggal",
        "booking",
        "created_at",
    )
    list_filter = ("tanggal", "item", "therapist")
    search_fields = ("item__nama_barang", "therapist__name", "booking__booking_id")
    raw_id_fields = ("item", "therapist", "booking")

