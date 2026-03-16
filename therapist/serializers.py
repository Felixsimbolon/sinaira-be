from rest_framework import serializers

from .models import Therapist


class TherapistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Therapist
        fields = [
            "id",
            "username",
            "name",
            "email",
            "license_number",
            "specialization",
            "years_experience",
            "consultation_rate",
            "kota",
            "kelurahan",
            "kecamatan",
            "latitude",
            "longitude",
            "is_active",
            "bio",
            "created_at",
            "updated_at",
        ]

