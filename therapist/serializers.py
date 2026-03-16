from rest_framework import serializers

from booking.utils import geocode_location_from_address

from .models import Therapist


def _has_minimum_address_for_geocode(alamat, kelurahan, kecamatan, kota):
    has_area = bool((alamat or '').strip() or (kelurahan or '').strip() or (kecamatan or '').strip())
    has_city = bool((kota or '').strip())
    return has_area and has_city


def _resolve_geocode(alamat, kelurahan, kecamatan, kota):
    if not _has_minimum_address_for_geocode(alamat, kelurahan, kecamatan, kota):
        return None, None

    return geocode_location_from_address(
        alamat=alamat or '',
        kelurahan=kelurahan or '',
        kecamatan=kecamatan or '',
        kota=kota or '',
    )


class BaseTherapistSerializer(serializers.ModelSerializer):
    def validate_no_hp(self, value):
        if value in (None, ''):
            return value
        if not value.isdigit():
            raise serializers.ValidationError('Nomor HP harus berisi angka saja.')
        if len(value) < 10 or len(value) > 15:
            raise serializers.ValidationError('Nomor HP harus antara 10-15 digit.')
        return value


class TherapistCreateSerializer(BaseTherapistSerializer):
    class Meta:
        model = Therapist
        fields = [
            'id',
            'username',
            'name',
            'email',
            'no_hp',
            'license_number',
            'specialization',
            'years_experience',
            'consultation_rate',
            'alamat',
            'kota',
            'kelurahan',
            'kecamatan',
            'is_active',
            'bio',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        latitude, longitude = _resolve_geocode(
            validated_data.get('alamat'),
            validated_data.get('kelurahan'),
            validated_data.get('kecamatan'),
            validated_data.get('kota'),
        )
        validated_data['latitude'] = latitude
        validated_data['longitude'] = longitude
        return super().create(validated_data)


class TherapistSerializer(BaseTherapistSerializer):
    class Meta:
        model = Therapist
        fields = [
            "id",
            "username",
            "name",
            "email",
            "no_hp",
            "license_number",
            "specialization",
            "years_experience",
            "consultation_rate",
            "alamat",
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

    def update(self, instance, validated_data):
        address_fields = {'alamat', 'kelurahan', 'kecamatan', 'kota'}
        should_regeocode = any(field in validated_data for field in address_fields)

        if should_regeocode:
            alamat = validated_data.get('alamat', instance.alamat)
            kelurahan = validated_data.get('kelurahan', instance.kelurahan)
            kecamatan = validated_data.get('kecamatan', instance.kecamatan)
            kota = validated_data.get('kota', instance.kota)
            latitude, longitude = _resolve_geocode(alamat, kelurahan, kecamatan, kota)
            validated_data['latitude'] = latitude
            validated_data['longitude'] = longitude

        return super().update(instance, validated_data)

