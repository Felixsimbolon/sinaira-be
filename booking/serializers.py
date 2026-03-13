from rest_framework import serializers
from .models import Booking
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
import re

User = get_user_model()


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

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'no_hp',
            'jadwal',
            'perawatan_pilihan',
            'status',
        ]

    def get_jadwal(self, obj):
        """Combine date and time for display."""
        return f"{obj.tgl_treatment} {obj.jam_treatment.strftime('%H:%M')}"


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
            'kota',
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


class BookingHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for customer booking history.
    """

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
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
        instance.update_status(validated_data['status'])
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
        instance.update_status(validated_data['status'])
        return instance


class BookingAssignTherapistSerializer(serializers.ModelSerializer):
    """Serializer for assigning therapist to booking in CONFIRMED status."""

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

        if booking.status in [
            Booking.BookingStatus.CANCELLED,
            Booking.BookingStatus.COMPLETED,
        ]:
            raise serializers.ValidationError(
                {'status': 'Booking dengan status CANCELLED atau COMPLETED tidak dapat di-assign therapist.'}
            )

        if booking.status != Booking.BookingStatus.CONFIRMED:
            raise serializers.ValidationError(
                {'status': 'Therapist hanya dapat di-assign ketika booking berstatus CONFIRMED.'}
            )

        return attrs

    def update(self, instance, validated_data):
        therapist = validated_data['therapist']
        instance.assign_therapist(therapist)
        return instance
