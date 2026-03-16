from django.contrib import admin
from .models import Layanan


@admin.register(Layanan)
class LayananAdmin(admin.ModelAdmin):
	list_display = ("id", "nama", "harga", "created_at")
	search_fields = ("nama",)
	ordering = ("nama",)
