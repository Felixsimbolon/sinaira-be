from django.contrib import admin
from .models import Layanan, LayananKategori, LayananSupplyConfig


@admin.register(LayananKategori)
class LayananKategoriAdmin(admin.ModelAdmin):
	list_display = ("kategori_id", "nama", "created_at")
	search_fields = ("kategori_id", "nama")
	ordering = ("nama",)


class LayananSupplyConfigInline(admin.TabularInline):
	model = LayananSupplyConfig
	extra = 1
	fk_name = "layanan"


@admin.register(Layanan)
class LayananAdmin(admin.ModelAdmin):
	list_display = ("layanan_id", "nama", "kategori", "durasi_menit", "harga", "is_active", "is_deleted", "created_at")
	list_filter = ("kategori", "is_active", "is_deleted")
	search_fields = ("layanan_id", "nama", "kategori__nama")
	ordering = ("kategori__nama", "nama")
	inlines = [LayananSupplyConfigInline]


@admin.register(LayananSupplyConfig)
class LayananSupplyConfigAdmin(admin.ModelAdmin):
	list_display = ("layanan", "item", "jumlah_per_use", "is_deleted", "created_at")
	list_filter = ("is_deleted", "layanan__kategori")
	search_fields = ("layanan__nama", "item__nama_barang")
