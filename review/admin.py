from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "booking",
        "therapist",
        "customer",
        "rating",
        "created_at",
    ]
    list_filter = ["rating", "created_at"]
    search_fields = [
        "booking__booking_id",
        "therapist__name",
        "customer__username",
        "comment",
    ]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]
