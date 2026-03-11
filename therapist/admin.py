from django.contrib import admin

from .models import Therapist


@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "name", "email", "license_number")
    search_fields = ("username", "name", "email", "license_number")
