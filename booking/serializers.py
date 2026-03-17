from rest_framework import serializers
from .models import Booking, BookingChangeLog
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
import re

from .utils import geocode_location_from_address
from therapist.utils import is_therapist_user_available_for_booking

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


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating bookings.
    Supports both anonymous and authenticated bookings.
    """

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'alamat',
            'kelurahan',
            'kecamatan',
            'kota',
            'no_hp',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'aromatherapy_oil',
            'kondisi_khusus',
            'tahu_dari',
            'notes',
            'voucher_code',
            'status',
            'created_at',
        ]
        read_only_fields = ['booking_id', 'status', 'created_at']

    def validate_no_hp(self, value):
        """Validate that phone number contains only digits."""
        if not value.isdigit():
            raise serializers.ValidationError("Nomor HP harus berisi angka saja.")
        if len(value) < 10 or len(value) > 15:
            raise serializers.ValidationError("Nomor HP harus antara 10-15 digit.")
        return value

    def validate_tgl_treatment(self, value):
        """Validate that treatment date is not in the past."""
        today = date.today()
        if value < today:
            raise serializers.ValidationError("Tanggal treatment tidak boleh di masa lalu.")
        return value

    def create(self, validated_data):
        # If user is authenticated, link the booking to their account
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Check if user is a customer (not staff)
            # Since staff users have roles, we don't link staff bookings
            if not hasattr(request.user, 'role'):
                validated_data['user'] = request.user

        latitude, longitude = _resolve_geocode(
            validated_data.get('alamat'),
            validated_data.get('kelurahan'),
            validated_data.get('kecamatan'),
            validated_data.get('kota'),
        )
        validated_data['latitude'] = latitude
        validated_data['longitude'] = longitude
        
        return super().create(validated_data)


class TherapistSerializer(serializers.ModelSerializer):
    """Serializer for therapist information."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'name']


class BookingListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing bookings in admin view.
    Shows: ID booking, Nama customer, Jadwal, Layanan, Status
    """
    jadwal = serializers.SerializerMethodField()
    has_review = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'no_hp',
            'jadwal',
            'perawatan_pilihan',
            'status',
            'has_review',
        ]

    def get_jadwal(self, obj):
        """Combine date and time for display."""
        return f"{obj.tgl_treatment} {obj.jam_treatment.strftime('%H:%M')}"

    def get_has_review(self, obj):
        return hasattr(obj, 'review')


class BookingDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed booking view.
    Returns complete booking information including assigned therapist.
    """
    therapist = TherapistSerializer(read_only=True)
    therapist_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='THERAPIST'),
        source='therapist',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'alamat',
            'kelurahan',
            'kecamatan',
            'kota',
            'latitude',
            'longitude',
            'no_hp',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'aromatherapy_oil',
            'kondisi_khusus',
            'tahu_dari',
            'status',
            'therapist',
            'therapist_id',
            'notes',
            'voucher_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['booking_id', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        old_snapshot = instance._get_audit_snapshot()
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

        updated_instance = super().update(instance, validated_data)

        request = self.context.get('request')
        changed_by = request.user if request and request.user.is_authenticated else None
        updated_instance.create_change_logs_from_snapshot(old_snapshot, changed_by=changed_by)

        return updated_instance


class BookingHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for customer booking history.
    """

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'alamat',
            'kelurahan',
            'kecamatan',
            'kota',
            'latitude',
            'longitude',
            'no_hp',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'aromatherapy_oil',
            'kondisi_khusus',
            'status',
            'created_at',
        ]
        read_only_fields = fields


class BookingStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for status updates by authorized staff users."""

    class Meta:
        model = Booking
        fields = ['status']

    def validate_status(self, value):
        booking = self.instance
        if booking is None:
            return value

        if value == Booking.BookingStatus.CHECKED_IN and booking.therapist_id is None:
            raise serializers.ValidationError(
                'Booking harus memiliki therapist yang ditugaskan sebelum CHECKED_IN.'
            )

        if not booking.can_transition_to(value):
            raise serializers.ValidationError(
                f'Transisi status dari {booking.status} ke {value} tidak diperbolehkan.'
            )

        return value

    def update(self, instance, validated_data):
        request = self.context.get('request')
        changed_by = request.user if request and request.user.is_authenticated else None
        instance.update_status(validated_data['status'], changed_by=changed_by)
        return instance


class TherapistBookingStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for status updates that can be performed by assigned therapist."""

    class Meta:
        model = Booking
        fields = ['status']

    def validate(self, attrs):
        booking = self.instance
        request = self.context.get('request')
        new_status = attrs.get('status')

        if booking is None:
            return attrs

        if booking.therapist_id is None:
            raise serializers.ValidationError(
                {'status': 'Booking belum memiliki therapist yang ditugaskan.'}
            )

        if not request or request.user.id != booking.therapist_id:
            raise serializers.ValidationError(
                {'status': 'Anda hanya dapat mengubah status booking yang ditugaskan kepada Anda.'}
            )

        allowed_statuses = {
            Booking.BookingStatus.CHECKED_IN,
            Booking.BookingStatus.CHECKED_OUT,
        }
        if new_status not in allowed_statuses:
            raise serializers.ValidationError(
                {'status': 'Therapist hanya dapat mengubah status ke CHECKED_IN atau CHECKED_OUT.'}
            )

        if not booking.can_transition_to(new_status):
            raise serializers.ValidationError(
                {'status': f'Transisi status dari {booking.status} ke {new_status} tidak diperbolehkan.'}
            )

        return attrs

    def update(self, instance, validated_data):
        request = self.context.get('request')
        changed_by = request.user if request and request.user.is_authenticated else None
        instance.update_status(validated_data['status'], changed_by=changed_by)
        return instance


class BookingAssignTherapistSerializer(serializers.ModelSerializer):
    """Serializer for assigning/reassigning therapist in CONFIRMED or ASSIGNED status."""

    therapist_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='THERAPIST'),
        source='therapist',
        write_only=True,
    )
    therapist = TherapistSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ['therapist_id', 'therapist', 'status']
        read_only_fields = ['therapist', 'status']

    def validate(self, attrs):
        booking = self.instance
        if booking is None:
            return attrs

        allowed_statuses = [
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.ASSIGNED,
        ]
        if booking.status not in allowed_statuses:
            raise serializers.ValidationError(
                {'status': 'Therapist hanya dapat di-assign/reassign ketika booking berstatus CONFIRMED atau ASSIGNED.'}
            )

        therapist = attrs.get('therapist')
        if therapist and not is_therapist_user_available_for_booking(
            therapist,
            booking.tgl_treatment,
            booking.jam_treatment,
        ):
            raise serializers.ValidationError(
                {'therapist_id': 'Therapist tidak tersedia pada jadwal booking tersebut.'}
            )

        return attrs

    def update(self, instance, validated_data):
        therapist = validated_data['therapist']
        request = self.context.get('request')
        changed_by = request.user if request and request.user.is_authenticated else None
        instance.assign_therapist(therapist, changed_by=changed_by)
        return instance


class BookingChangeLogSerializer(serializers.ModelSerializer):
    changed_by = TherapistSerializer(read_only=True)

    class Meta:
        model = BookingChangeLog
        fields = [
            'id',
            'field_name',
            'old_value',
            'new_value',
            'changed_by',
            'changed_at',
        ]


class BookingGeocodeSerializer(serializers.Serializer):
    """Serializer for geocoding request payload."""

    alamat = serializers.CharField(required=False, allow_blank=True)
    kelurahan = serializers.CharField(required=False, allow_blank=True)
    kecamatan = serializers.CharField(required=False, allow_blank=True)
    kota = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        alamat = attrs.get('alamat', '').strip()
        kelurahan = attrs.get('kelurahan', '').strip()

        if not alamat and not kelurahan:
            raise serializers.ValidationError(
                {'error': 'Minimal salah satu field alamat atau kelurahan harus diisi.'}
            )

        return attrs
