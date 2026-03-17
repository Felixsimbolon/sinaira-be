from rest_framework import serializers

from .models import Layanan


class LayananSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layanan
        fields = ["id", "nama", "harga", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_harga(self, value):
        if value <= 0:
            raise serializers.ValidationError("Harga harus lebih dari 0.")
        return value
