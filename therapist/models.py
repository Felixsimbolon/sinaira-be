from django.db import models


class Therapist(models.Model):
    username = models.CharField(max_length=150, unique=True, blank=True, default="")
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    license_number = models.CharField(max_length=100, blank=True, default="")

    specialization = models.CharField(max_length=255, blank=True, default="")
    years_experience = models.PositiveIntegerField(default=0)
    consultation_rate = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    bio = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.license_number or 'no-license'})"
