from rest_framework import serializers

from booking.utils import geocode_location_from_address

from .models import Therapist, TherapistDateOverride, TherapistWeeklyAvailability


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


class TherapistWeeklyAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TherapistWeeklyAvailability
        fields = [
            'id',
            'therapist',
            'day_of_week',
            'start_time',
            'end_time',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'therapist', 'created_at', 'updated_at']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        therapist = self.context.get('therapist')

        if therapist is None and instance is None:
            raise serializers.ValidationError({'therapist': 'Therapist context is required.'})
        if therapist is None and instance is not None:
            therapist = instance.therapist

        day_of_week = attrs.get('day_of_week', instance.day_of_week if instance else None)
        start_time = attrs.get('start_time', instance.start_time if instance else None)
        end_time = attrs.get('end_time', instance.end_time if instance else None)

        if start_time is None or end_time is None:
            raise serializers.ValidationError(
                {'time': 'start_time dan end_time wajib diisi.'}
            )

        if start_time >= end_time:
            raise serializers.ValidationError(
                {'time': 'start_time harus lebih kecil dari end_time.'}
            )

        overlap_qs = TherapistWeeklyAvailability.objects.filter(
            therapist=therapist,
            day_of_week=day_of_week,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if instance is not None:
            overlap_qs = overlap_qs.exclude(id=instance.id)

        if overlap_qs.exists():
            raise serializers.ValidationError(
                {'time': 'Slot jadwal mingguan overlap dengan slot lain pada hari yang sama.'}
            )

        return attrs

    def create(self, validated_data):
        therapist = self.context['therapist']
        validated_data['therapist'] = therapist
        return super().create(validated_data)


class TherapistDateOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = TherapistDateOverride
        fields = [
            'id',
            'therapist',
            'date',
            'start_time',
            'end_time',
            'is_available',
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'therapist', 'created_at', 'updated_at']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        therapist = self.context.get('therapist')

        if therapist is None and instance is None:
            raise serializers.ValidationError({'therapist': 'Therapist context is required.'})
        if therapist is None and instance is not None:
            therapist = instance.therapist

        target_date = attrs.get('date', instance.date if instance else None)
        is_available = attrs.get('is_available', instance.is_available if instance else True)
        start_time = attrs.get('start_time', instance.start_time if instance else None)
        end_time = attrs.get('end_time', instance.end_time if instance else None)

        off_qs = TherapistDateOverride.objects.filter(
            therapist=therapist,
            date=target_date,
            is_available=False,
        )
        available_qs = TherapistDateOverride.objects.filter(
            therapist=therapist,
            date=target_date,
            is_available=True,
        )

        if instance is not None:
            off_qs = off_qs.exclude(id=instance.id)
            available_qs = available_qs.exclude(id=instance.id)

        if not is_available:
            if start_time is not None or end_time is not None:
                raise serializers.ValidationError(
                    {'time': 'start_time dan end_time harus kosong jika is_available = false.'}
                )
            if available_qs.exists():
                raise serializers.ValidationError(
                    {'date': 'Tidak bisa menambahkan off-day jika slot available pada tanggal tersebut sudah ada.'}
                )
            return attrs

        if start_time is None or end_time is None:
            raise serializers.ValidationError(
                {'time': 'start_time dan end_time wajib diisi jika is_available = true.'}
            )

        if start_time >= end_time:
            raise serializers.ValidationError(
                {'time': 'start_time harus lebih kecil dari end_time.'}
            )

        if off_qs.exists():
            raise serializers.ValidationError(
                {'date': 'Tanggal ini sudah ditandai off-day.'}
            )

        overlap_qs = available_qs.filter(
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if overlap_qs.exists():
            raise serializers.ValidationError(
                {'time': 'Slot override overlap dengan slot override lain pada tanggal yang sama.'}
            )

        return attrs

    def create(self, validated_data):
        therapist = self.context['therapist']
        validated_data['therapist'] = therapist
        return super().create(validated_data)

