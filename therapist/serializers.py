from datetime import time

from django.contrib.auth import get_user_model
from rest_framework import serializers

from booking.utils import geocode_location_from_address

from .models import Therapist, TherapistDateOverride, TherapistWeeklyAvailability

User = get_user_model()


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
    def to_internal_value(self, data):
        normalized_data = data.copy() if hasattr(data, 'copy') else dict(data)

        legacy_address = normalized_data.pop('address', None)
        alamat = normalized_data.get('alamat')
        if (alamat is None or str(alamat).strip() == '') and legacy_address not in (None, ''):
            normalized_data['alamat'] = legacy_address

        return super().to_internal_value(normalized_data)

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
        # We handle uniqueness manually to support "upsert" behaviour when
        # a Therapist with the same username/email already exists.
        extra_kwargs = {
            'username': {'validators': []},
            'email': {'validators': []},
        }

    def create(self, validated_data):
        latitude, longitude = _resolve_geocode(
            validated_data.get('alamat'),
            validated_data.get('kelurahan'),
            validated_data.get('kecamatan'),
            validated_data.get('kota'),
        )
        validated_data['latitude'] = latitude
        validated_data['longitude'] = longitude
        # Upsert behaviour:
        # - If a Therapist with the same email/username already exists,
        #   update that record instead of creating a new one.
        # - Otherwise create a new Therapist.
        therapist = (
            Therapist.objects.filter(email=validated_data.get('email')).first()
            or Therapist.objects.filter(username=validated_data.get('username')).first()
        )

        if therapist:
            for field, value in validated_data.items():
                setattr(therapist, field, value)
            therapist.save()
        else:
            therapist = super().create(validated_data)

        # Link to an existing THERAPIST account (created from Akun page)
        # so that Therapists page and Akun stay in sync.
        user = (
            User.objects.filter(
                email=therapist.email,
                role=User.Role.THERAPIST,
            ).first()
            or User.objects.filter(
                username=therapist.username,
                role=User.Role.THERAPIST,
            ).first()
        )

        if user:
            therapist.user = user
            therapist.save(update_fields=['user'])

            # Keep basic identity fields in sync with the therapist profile.
            user.name = therapist.name
            if therapist.username:
                user.username = therapist.username
            user.email = therapist.email
            user.save(update_fields=['name', 'username', 'email'])

        return therapist


class TherapistSerializer(BaseTherapistSerializer):
    address = serializers.CharField(source='alamat', read_only=True)

    class Meta:
        model = Therapist
        fields = [
            "id",
            "user",
            "username",
            "name",
            "email",
            "no_hp",
            "license_number",
            "specialization",
            "years_experience",
            "consultation_rate",
            "address",
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
        read_only_fields = ["user", "created_at", "updated_at"]

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

        therapist = super().update(instance, validated_data)

        # Ensure therapist is linked to a THERAPIST account if possible.
        user = therapist.user
        if user is None:
            user = (
                User.objects.filter(
                    email=therapist.email,
                    role=User.Role.THERAPIST,
                ).first()
                or User.objects.filter(
                    username=therapist.username,
                    role=User.Role.THERAPIST,
                ).first()
            )
            if user:
                therapist.user = user
                therapist.save(update_fields=['user'])

        # Propagate basic identity changes back to linked User account so
        # the Akun page always reflects the latest therapist info.
        if user:
            if 'name' in validated_data:
                user.name = therapist.name
            if 'username' in validated_data and therapist.username:
                user.username = therapist.username
            if 'email' in validated_data:
                user.email = therapist.email
            user.save(update_fields=['name', 'username', 'email'])

        return therapist


class TherapistWeeklyAvailabilitySerializer(serializers.ModelSerializer):
    GRID_START_TIME = time(7, 0)
    GRID_END_TIME = time(20, 0)

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

        if start_time < self.GRID_START_TIME or end_time > self.GRID_END_TIME:
            raise serializers.ValidationError(
                {'time': 'Slot jadwal harus berada dalam rentang 07:00-20:00.'}
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
    GRID_START_TIME = time(7, 0)
    GRID_END_TIME = time(20, 0)

    class Meta:
        model = TherapistDateOverride
        fields = [
            'id',
            'therapist',
            'date',
            'start_time',
            'end_time',
            'override_type',
            'is_active',
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
        override_type = attrs.get(
            'override_type',
            instance.override_type if instance else TherapistDateOverride.OverrideType.UNAVAILABLE,
        )
        start_time = attrs.get('start_time', instance.start_time if instance else None)
        end_time = attrs.get('end_time', instance.end_time if instance else None)
        is_active = attrs.get('is_active', instance.is_active if instance else True)

        same_type_qs = TherapistDateOverride.objects.filter(
            therapist=therapist,
            date=target_date,
            override_type=override_type,
            is_active=True,
        )

        if instance is not None:
            same_type_qs = same_type_qs.exclude(id=instance.id)

        if not is_active:
            return attrs

        if start_time is None or end_time is None:
            raise serializers.ValidationError(
                {'time': 'start_time dan end_time wajib diisi.'}
            )

        if start_time >= end_time:
            raise serializers.ValidationError(
                {'time': 'start_time harus lebih kecil dari end_time.'}
            )

        if start_time < self.GRID_START_TIME or end_time > self.GRID_END_TIME:
            raise serializers.ValidationError(
                {'time': 'Slot override harus berada dalam rentang 07:00-20:00.'}
            )

        overlap_qs = same_type_qs.filter(
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

