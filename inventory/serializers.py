from rest_framework import serializers

from .models import Inventory


class InventorySerializer(serializers.ModelSerializer):
    """Baca + status_stok terhitung."""

    status_stok = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = [
            "id",
            "nama_barang",
            "kategori",
            "lokasi",
            "jumlah_stok",
            "threshold_minimum",
            "status_stok",
            "keterangan",
        ]
        read_only_fields = ["id", "status_stok"]

    def get_status_stok(self, obj: Inventory) -> str:
        if obj.jumlah_stok <= obj.threshold_minimum:
            return "Low Stock"
        return "Normal"


class InventoryWriteSerializer(serializers.ModelSerializer):
    """Create / full update (PUT)."""

    class Meta:
        model = Inventory
        fields = [
            "nama_barang",
            "kategori",
            "lokasi",
            "jumlah_stok",
            "threshold_minimum",
            "keterangan",
        ]

    def validate_nama_barang(self, value: str) -> str:
        if not (value or "").strip():
            raise serializers.ValidationError("Nama barang wajib diisi.")
        return value.strip()

    def validate_kategori(self, value: str) -> str:
        valid = {c[0] for c in Inventory.Kategori.choices}
        if value not in valid:
            raise serializers.ValidationError("Kategori tidak valid.")
        return value

    def validate_lokasi(self, value: str) -> str:
        valid = {c[0] for c in Inventory.Lokasi.choices}
        if value not in valid:
            raise serializers.ValidationError("Lokasi tidak valid.")
        return value

    def validate_jumlah_stok(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("Jumlah stok tidak boleh negatif.")
        return value

    def validate_threshold_minimum(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("Threshold minimum tidak boleh negatif.")
        return value

    def validate_keterangan(self, value):
        if value is None:
            return ""
        return value
