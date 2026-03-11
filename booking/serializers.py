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
