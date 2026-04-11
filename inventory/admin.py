from django.contrib import admin

from .models import Inventory


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "nama_barang",
        "kategori",
        "lokasi",
        "jumlah_stok",
        "threshold_minimum",
        "is_deleted",
        "updated_at",
    )
    list_filter = ("is_deleted", "kategori", "lokasi")
    search_fields = ("nama_barang", "kategori", "keterangan")
