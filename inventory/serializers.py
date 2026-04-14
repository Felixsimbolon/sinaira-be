from rest_framework import serializers

from .models import Inventory, TherapistSupplyAssignment
from therapist.models import Therapist


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
            "usage_per_unit",
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
            "usage_per_unit",
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

    def validate_usage_per_unit(self, value: int) -> int:
        if value is not None and value < 1:
            raise serializers.ValidationError("Usage per unit harus minimal 1.")
        return value

    def validate_keterangan(self, value):
        if value is None:
            return ""
        return value


# ── Assignment Serializers ────────────────────────────────────────────


class AssignmentReadSerializer(serializers.ModelSerializer):
    """Read-only serializer untuk daftar assignment."""

    item_id = serializers.IntegerField(source="item.id", read_only=True)
    therapist_id = serializers.IntegerField(source="therapist.id", read_only=True)
    item_name = serializers.CharField(source="item.nama_barang", read_only=True)
    therapist_name = serializers.CharField(source="therapist.name", read_only=True)
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TherapistSupplyAssignment
        fields = [
            "id",
            "item_id",
            "item_name",
            "therapist_id",
            "therapist_name",
            "quantity_assigned",
            "usage_per_unit",
            "total_usage",
            "remaining_usage",
            "status",
            "notes",
            "assigned_at",
            "assigned_by",
            "assigned_by_name",
        ]
        read_only_fields = fields

    def get_assigned_by_name(self, obj) -> str | None:
        if obj.assigned_by:
            return obj.assigned_by.name or obj.assigned_by.username
        return None


class AssignmentCreateSerializer(serializers.Serializer):
    """Create assignment (POST)."""

    item_id = serializers.IntegerField()
    therapist_id = serializers.IntegerField()
    quantity_assigned = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_quantity_assigned(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError(
                "quantityAssigned harus integer positif (> 0)."
            )
        return value

    def validate_item_id(self, value: int) -> int:
        try:
            item = Inventory.objects.get(pk=value, is_deleted=False)
        except Inventory.DoesNotExist:
            raise serializers.ValidationError(
                "Item tidak ditemukan atau sudah dihapus."
            )
        if item.usage_per_unit < 1:
            raise serializers.ValidationError(
                "usagePerUnit item tidak valid (harus > 0)."
            )
        return value

    def validate_therapist_id(self, value: int) -> int:
        try:
            Therapist.objects.get(pk=value, is_active=True)
        except Therapist.DoesNotExist:
            raise serializers.ValidationError(
                "Therapist tidak ditemukan atau tidak aktif."
            )
        return value

    def validate(self, attrs):
        item_id = attrs.get("item_id")
        quantity = attrs.get("quantity_assigned")

        if item_id and quantity:
            try:
                item = Inventory.objects.get(pk=item_id, is_deleted=False)
            except Inventory.DoesNotExist:
                raise serializers.ValidationError(
                    {"item_id": "Item tidak ditemukan atau sudah dihapus."}
                )

            if quantity > item.jumlah_stok:
                raise serializers.ValidationError(
                    {
                        "quantity_assigned": (
                            f"Quantity melebihi stok tersedia "
                            f"({item.jumlah_stok} tersisa)."
                        )
                    }
                )

        return attrs


class AssignmentUpdateSerializer(serializers.Serializer):
    """Update assignment (PATCH) — hanya quantity_assigned dan notes."""

    quantity_assigned = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_quantity_assigned(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError(
                "quantityAssigned harus integer positif (> 0)."
            )
        return value

    def validate(self, attrs):
        quantity = attrs.get("quantity_assigned")
        assignment = self.context.get("assignment")

        if quantity is not None and assignment:
            item = assignment.item
            if item.is_deleted:
                raise serializers.ValidationError(
                    {"item_id": "Item sudah dihapus."}
                )

            # Stok yang tersedia = stok saat ini + quantity lama (karena akan dikembalikan)
            available = item.jumlah_stok + assignment.quantity_assigned
            if quantity > available:
                raise serializers.ValidationError(
                    {
                        "quantity_assigned": (
                            f"Quantity melebihi stok tersedia "
                            f"({available} tersisa setelah pengembalian)."
                        )
                    }
                )

        return attrs

