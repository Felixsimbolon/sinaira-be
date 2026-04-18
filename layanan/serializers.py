from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from inventory.models import Inventory
from .models import Layanan, LayananKategori, LayananSupplyConfig


class LayananKategoriSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="kategori_id", read_only=True)

    class Meta:
        model = LayananKategori
        fields = ["id", "nama", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class KebutuhanBahanItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    jumlah_per_use = serializers.IntegerField()

    def validate_jumlah_per_use(self, value):
        if value <= 0:
            raise serializers.ValidationError("Jumlah per use harus lebih dari 0.")
        return value

    def validate_item_id(self, value):
        try:
            Inventory.objects.get(pk=value, is_deleted=False)
        except Inventory.DoesNotExist:
            raise serializers.ValidationError("Item tidak ditemukan atau sudah dihapus.")
        return value


class KebutuhanBahanReadSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField(source="item.id")
    item_name = serializers.CharField(source="item.nama_barang")

    class Meta:
        model = LayananSupplyConfig
        fields = ["id", "item_id", "item_name", "jumlah_per_use"]


class LayananSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="layanan_id", read_only=True)
    kategori_id = serializers.SlugRelatedField(
        source="kategori",
        slug_field="kategori_id",
        queryset=LayananKategori.objects.all(),
    )
    kategori = LayananKategoriSerializer(read_only=True)
    kebutuhan_bahan = serializers.ListField(
        child=KebutuhanBahanItemSerializer(),
        write_only=True,
        required=False,
    )

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
            "kebutuhan_bahan",
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

    def validate_kebutuhan_bahan(self, value):
        item_ids = [item['item_id'] for item in value]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("Tidak boleh ada item yang duplikat dalam daftar kebutuhan_bahan.")
        return value

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Prefetched in views.py if possible, otherwise regular query
        configs = instance.supply_configs.filter(is_deleted=False)
        ret["kebutuhan_bahan"] = KebutuhanBahanReadSerializer(configs, many=True).data
        return ret

    def create(self, validated_data):
        kebutuhan_bahan = validated_data.pop("kebutuhan_bahan", [])
        
        with transaction.atomic():
            layanan = super().create(validated_data)
            self._sync_kebutuhan_bahan(layanan, kebutuhan_bahan)
            
        return layanan

    def update(self, instance, validated_data):
        # We use a specific check to see if it was provided in the input data
        # because pop with default might overwrite an intention to clear the array.
        has_kebutuhan = "kebutuhan_bahan" in validated_data
        kebutuhan_bahan = validated_data.pop("kebutuhan_bahan", [])
        
        with transaction.atomic():
            layanan = super().update(instance, validated_data)
            if has_kebutuhan:
                self._sync_kebutuhan_bahan(layanan, kebutuhan_bahan)

        return layanan

    def _sync_kebutuhan_bahan(self, layanan, payload_items):
        existing_configs = LayananSupplyConfig.objects.filter(layanan=layanan)
        existing_map = {config.item_id: config for config in existing_configs}
        
        payload_item_ids = {item["item_id"] for item in payload_items}
        
        # 1. Soft delete configs not in payload
        for item_id, config in existing_map.items():
            if item_id not in payload_item_ids and not config.is_deleted:
                config.is_deleted = True
                config.deleted_at = timezone.now()
                config.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
                
        # 2. Upsert configs from payload
        for item_data in payload_items:
            item_id = item_data["item_id"]
            jumlah = item_data["jumlah_per_use"]
            
            if item_id in existing_map:
                config = existing_map[item_id]
                # Update if needed or if it was soft deleted
                if config.is_deleted or config.jumlah_per_use != jumlah:
                    config.is_deleted = False
                    config.deleted_at = None
                    config.jumlah_per_use = jumlah
                    config.save(update_fields=["is_deleted", "deleted_at", "jumlah_per_use", "updated_at"])
            else:
                LayananSupplyConfig.objects.create(
                    layanan=layanan,
                    item_id=item_id,
                    jumlah_per_use=jumlah
                )
