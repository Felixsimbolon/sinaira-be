from rest_framework import serializers
from rest_framework.exceptions import NotFound

from inventory.models import Inventory

from .models import SupplyRequest


class SupplyRequestInventoryItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="nama_barang", read_only=True)

    class Meta:
        model = Inventory
        fields = ["id", "name"]
        read_only_fields = fields


class SupplyRequestReadSerializer(serializers.ModelSerializer):
    itemId = serializers.IntegerField(source="item_id", read_only=True)
    itemName = serializers.CharField(source="item.nama_barang", read_only=True)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = SupplyRequest
        fields = [
            "id",
            "itemId",
            "itemName",
            "quantity",
            "reason",
            "status",
            "createdBy",
            "createdAt",
        ]
        read_only_fields = fields

    def get_createdBy(self, obj: SupplyRequest) -> str:
        if obj.created_by.name:
            return obj.created_by.name
        return obj.created_by.username


class SupplyRequestCreateSerializer(serializers.ModelSerializer):
    itemId = serializers.IntegerField(required=True, write_only=True)
    reason = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = SupplyRequest
        fields = ["itemId", "quantity", "reason"]

    def validate_itemId(self, value: int) -> int:
        item = Inventory.objects.filter(pk=value, is_deleted=False).first()
        if item is None:
            raise NotFound("Item inventory tidak ditemukan atau sudah nonaktif.")

        self.context["inventory_item"] = item
        return value

    def validate_quantity(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("quantity harus lebih besar dari 0.")
        return value

    def validate_reason(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("reason wajib diisi.")
        return cleaned

    def create(self, validated_data):
        validated_data.pop("itemId", None)
        item = self.context["inventory_item"]
        request = self.context["request"]

        return SupplyRequest.objects.create(
            item=item,
            quantity=validated_data["quantity"],
            reason=validated_data["reason"],
            status=SupplyRequest.Status.PENDING,
            created_by=request.user,
        )


class SupplyRequestStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[SupplyRequest.Status.APPROVED, SupplyRequest.Status.REJECTED],
        required=True,
    )

    def validate(self, attrs):
        allowed_keys = {"status"}
        payload_keys = set(self.initial_data.keys())
        if payload_keys - allowed_keys:
            raise serializers.ValidationError(
                {"error": "Payload hanya boleh berisi field status."}
            )
        return attrs
