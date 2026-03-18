from rest_framework import serializers

from .models import Layanan, LayananKategori


class LayananKategoriSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="kategori_id", read_only=True)

    class Meta:
        model = LayananKategori
        fields = ["id", "nama", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class LayananSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="layanan_id", read_only=True)
    kategori_id = serializers.SlugRelatedField(
        source="kategori",
        slug_field="kategori_id",
        queryset=LayananKategori.objects.all(),
    )
    kategori = LayananKategoriSerializer(read_only=True)

    class Meta:
        model = Layanan
        fields = [
            "id",
            "kategori_id",
            "kategori",
            "nama",
            "durasi_menit",
            "deskripsi",
            "harga",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "deskripsi": {"required": False, "allow_blank": True, "allow_null": True},
        }

    def validate_durasi_menit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Durasi harus lebih dari 0 menit.")
        return value

    def validate_harga(self, value):
        if value <= 0:
            raise serializers.ValidationError("Harga harus lebih dari 0.")
        return value
