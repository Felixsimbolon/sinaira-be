from django.contrib import admin

from .models import Promo


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
	list_display = ("id", "title", "content_type", "posting_state", "start_date", "end_date", "deleted_at")
	list_filter = ("content_type", "posting_state")
	search_fields = ("title", "description")

# Register your models here.
