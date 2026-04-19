from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from .models import Booking, BookingChangeLog
from layanan.models import Layanan
from event.models import Promo
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


def _get_max_booking_date_from_today(today: date) -> date:
    try:
        return today.replace(year=today.year + 1)
    except ValueError:
        # Handle leap day: map Feb 29 to Feb 28 next year.
        return today.replace(year=today.year + 1, day=28)


class BookingCreateSerializer(serializers.ModelSerializer):
    MINIMUM_BOOKING_TOTAL = 180000
    promo_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'alamat',
            'kelurahan',
            'kecamatan',
            'kota',
            'kode_pos',
            'no_hp',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'layanans',
            'harga',
            'aromatherapy_oil',
            'kondisi_khusus',
            'tahu_dari',
            'notes',
            'voucher_code',
            'promo_id',
            'status',
            'created_at',
        ]
        read_only_fields = ['booking_id', 'status', 'harga', 'created_at']

    @staticmethod
    def _extract_selected_layanan_names(perawatan_pilihan: str) -> list[str]:
        if not perawatan_pilihan:
            return []

        names = [name.strip() for name in perawatan_pilihan.split(',') if name.strip()]
        # Keep order while removing duplicates.
        return list(dict.fromkeys(names))

    def _calculate_base_price_from_layanan(self, perawatan_pilihan: str):
        selected_names = self._extract_selected_layanan_names(perawatan_pilihan)
        if not selected_names:
            return None

        layanan_qs = Layanan.active_objects.filter(
            is_active=True,
            nama__in=selected_names,
        ).only('nama', 'harga')

        layanan_by_name = {}
        for layanan in layanan_qs:
            layanan_by_name.setdefault(layanan.nama, []).append(layanan)

        # If data layanan is incomplete/ambiguous, reject to keep price deterministic.
        missing_names = [name for name in selected_names if name not in layanan_by_name]
        has_ambiguous_name = any(len(items) > 1 for items in layanan_by_name.values())
        if missing_names or has_ambiguous_name:
            raise serializers.ValidationError(
                {
                    'perawatan_pilihan': (
                        'Perawatan pilihan tidak valid atau duplikat. '
                        'Pastikan layanan yang dipilih tersedia dan unik.'
                    )
                }
            )

        return sum(layanan_by_name[name][0].harga for name in selected_names)

    def _calculate_discount_amount(self, *, base_price: int, perawatan_pilihan: str, no_hp: str, promo_id: int | None, voucher_code: str | None) -> Decimal:
        base_amount = Decimal(str(base_price))

        if promo_id:
            promo = Promo.active_objects.filter(
                pk=promo_id,
                content_type=Promo.ContentType.PROMO,
                posting_state=Promo.PostingState.PUBLISHED,
                show_in_booking=True,
            ).first()
            if promo is None:
                raise serializers.ValidationError({'promo_id': 'Promo tidak tersedia.'})

            today = date.today()
            if promo.start_date and today < promo.start_date:
                raise serializers.ValidationError({'promo_id': 'Promo belum dimulai.'})
            if promo.end_date and today > promo.end_date:
                raise serializers.ValidationError({'promo_id': 'Promo sudah berakhir.'})

            selected_names = self._extract_selected_layanan_names(perawatan_pilihan)
            promo_service_names = set(promo.applicable_services.values_list('nama', flat=True))
            if promo_service_names and not set(selected_names).intersection(promo_service_names):
                raise serializers.ValidationError({'promo_id': 'Promo ini tidak berlaku untuk layanan yang dipilih.'})

            min_total_price = Decimal(str(promo.min_total_price)) if promo.min_total_price is not None else Decimal('0')
            if min_total_price and base_amount < min_total_price:
                raise serializers.ValidationError(
                    {'promo_id': f'Total minimal untuk promo ini adalah Rp {int(min_total_price):,}'.replace(',', '.')}
                )

            if promo.benefit_type == Promo.BenefitType.DISCOUNT_NOMINAL:
                discount = Decimal(str(promo.benefit_discount_amount or 0))
                return min(discount, base_amount)

            if promo.benefit_type == Promo.BenefitType.DISCOUNT_PERCENT:
                percent = Decimal(str(promo.benefit_discount_percent or 0))
                return (base_amount * percent / Decimal('100')).quantize(Decimal('1'))

            if promo.benefit_type == Promo.BenefitType.FREE_SERVICE and promo.benefit_free_service is not None:
                selected_names = self._extract_selected_layanan_names(perawatan_pilihan)
                if promo.benefit_free_service.nama not in selected_names:
                    raise serializers.ValidationError(
                        {'promo_id': 'Layanan gratis pada promo ini harus termasuk layanan yang dipilih.'}
                    )
                return min(Decimal(str(promo.benefit_free_service.harga)), base_amount)

            return Decimal('0')

        if voucher_code:
            match = re.match(r'^LOYALTY-(\d+)$', voucher_code.strip().upper())
            if match:
                required_visits = int(match.group(1))
                prior_count = Booking.objects.filter(no_hp=no_hp).count()
                if prior_count < required_visits:
                    raise serializers.ValidationError(
                        {'voucher_code': f'Voucher ini berlaku mulai kunjungan ke-{required_visits}.'}
                    )
                percent = Decimal(str(required_visits))
                return (base_amount * percent / Decimal('100')).quantize(Decimal('1'))

        return Decimal('0')

    def validate(self, attrs):
        attrs = super().validate(attrs)

        calculated_harga = self._calculate_base_price_from_layanan(
            attrs.get('perawatan_pilihan', ''),
        )

        if calculated_harga is None:
            raise serializers.ValidationError(
                {'perawatan_pilihan': 'Perawatan pilihan wajib diisi.'}
            )

        if calculated_harga < self.MINIMUM_BOOKING_TOTAL:
            raise serializers.ValidationError(
                {
                    'perawatan_pilihan': (
                        f'Total harga layanan minimal Rp {self.MINIMUM_BOOKING_TOTAL:,}.'.replace(',', '.')
                    )
                }
            )

        promo_id = attrs.get('promo_id')
        voucher_code = attrs.get('voucher_code')
        discount_amount = self._calculate_discount_amount(
            base_price=calculated_harga,
            perawatan_pilihan=attrs.get('perawatan_pilihan', ''),
            no_hp=attrs.get('no_hp', ''),
            promo_id=promo_id,
            voucher_code=voucher_code,
        )

        attrs['calculated_harga'] = calculated_harga
        attrs['calculated_total_pembayaran'] = max(Decimal(str(calculated_harga)) - discount_amount, Decimal('0'))
        return attrs

    def validate_no_hp(self, value):
        """Validate that phone number contains only digits."""
        if not value.isdigit():
            raise serializers.ValidationError("Nomor HP harus berisi angka saja.")
        if len(value) < 10 or len(value) > 15:
            raise serializers.ValidationError("Nomor HP harus antara 10-15 digit.")
        return value

    def validate_tgl_treatment(self, value):
        """Validate that treatment date is not in the past and not beyond 1 year."""
        today = date.today()
        max_booking_date = _get_max_booking_date_from_today(today)
        if value < today:
            raise serializers.ValidationError("Tanggal treatment tidak boleh di masa lalu.")
        if value > max_booking_date:
            raise serializers.ValidationError("Tanggal treatment maksimal 1 tahun dari hari ini.")
        return value

    def validate_kode_pos(self, value):
        """Optional postal code, if provided must be numeric and 5 digits."""
        if not value:
            return value

        if not value.isdigit():
            raise serializers.ValidationError("Kode pos harus berisi angka saja.")

        if len(value) != 5:
            raise serializers.ValidationError("Kode pos harus 5 digit.")

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

        calculated_harga = validated_data.pop('calculated_harga', None)
        if calculated_harga is not None:
            validated_data['harga'] = calculated_harga

        calculated_total = validated_data.pop('calculated_total_pembayaran', None)
        if calculated_total is not None:
            validated_data['total_pembayaran'] = calculated_total

        # promo_id is a write-only helper and not stored on the booking model.
        validated_data.pop('promo_id', None)
        
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
            'harga',
            'total_pembayaran',
            'status',
            'has_review',
        ]

    def get_jadwal(self, obj):
        """Combine date and time for display."""
        return f"{obj.tgl_treatment} {obj.jam_treatment.strftime('%H:%M')}"

    def get_has_review(self, obj):
        return hasattr(obj, 'review')


class TherapistBookingListSerializer(serializers.ModelSerializer):
    """
    Serializer for therapist's assigned bookings list (Sesi Saya).
    Includes alamat and kondisi_khusus for session cards.
    """
    jadwal = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'nama',
            'no_hp',
            'jadwal',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'alamat',
            'kondisi_khusus',
            'status',
        ]

    def get_jadwal(self, obj):
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
            'kelurahan',
            'kecamatan',
            'kota',
            'kode_pos',
            'latitude',
            'longitude',
            'no_hp',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'layanans',
            'harga',
            'total_pembayaran',
            'aromatherapy_oil',
            'kondisi_khusus',
            'tahu_dari',
            'status',
            'cancellation_reason',
            'therapist',
            'therapist_id',
            'notes',
            'voucher_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['booking_id', 'created_at', 'updated_at']

    def validate_tgl_treatment(self, value):
        today = date.today()
        max_booking_date = _get_max_booking_date_from_today(today)
        if value < today:
            raise serializers.ValidationError("Tanggal treatment tidak boleh di masa lalu.")
        if value > max_booking_date:
            raise serializers.ValidationError("Tanggal treatment maksimal 1 tahun dari hari ini.")
        return value

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
            'kode_pos',
            'latitude',
            'longitude',
            'no_hp',
            'tgl_treatment',
            'jam_treatment',
            'perawatan_pilihan',
            'aromatherapy_oil',
            'kondisi_khusus',
            'status',
            'cancellation_reason',
            'created_at',
        ]
        read_only_fields = fields


class BookingStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for status updates by authorized staff users."""

    class Meta:
        model = Booking
        fields = ['status', 'harga', 'total_pembayaran', 'cancellation_reason']

    def validate(self, attrs):
        booking = self.instance
        if booking is None:
            return attrs

        new_status = attrs.get('status')
        effective_status = new_status or booking.status
        harga = attrs.get('harga', booking.harga)
        total_pembayaran = attrs.get('total_pembayaran', booking.total_pembayaran)

        if new_status and not booking.can_transition_to(new_status):
            raise serializers.ValidationError(
                {'status': f'Transisi status dari {booking.status} ke {new_status} tidak diperbolehkan.'}
            )

        if effective_status == Booking.BookingStatus.CHECKED_IN and booking.therapist_id is None:
            raise serializers.ValidationError(
                {'status': 'Booking harus memiliki therapist yang ditugaskan sebelum CHECKED_IN.'}
            )

        if effective_status == Booking.BookingStatus.PAID:
            payment_errors = {}

            if total_pembayaran is None and harga is not None:
                # Allow simpler PAID transition: default total to harga when not provided.
                attrs['total_pembayaran'] = harga
                total_pembayaran = harga

            if harga is None:
                payment_errors['harga'] = 'Field harga wajib diisi sebelum status menjadi PAID.'
            if total_pembayaran is None:
                payment_errors['total_pembayaran'] = 'Field total_pembayaran wajib diisi sebelum status menjadi PAID.'

            if harga is not None and harga <= 0:
                payment_errors['harga'] = 'Harga harus lebih besar dari 0.'
            if total_pembayaran is not None and total_pembayaran <= 0:
                payment_errors['total_pembayaran'] = 'Total pembayaran harus lebih besar dari 0.'

            if payment_errors:
                raise serializers.ValidationError(payment_errors)

        if new_status == Booking.BookingStatus.CANCELLED:
            cancellation_reason = (attrs.get('cancellation_reason') or '').strip()
            if not cancellation_reason:
                raise serializers.ValidationError(
                    {'cancellation_reason': 'Alasan pembatalan wajib diisi saat status CANCELLED.'}
                )
            attrs['cancellation_reason'] = cancellation_reason

        if booking.status == Booking.BookingStatus.CONFIRMED and new_status in {
            Booking.BookingStatus.ASSIGNED,
            Booking.BookingStatus.CHECKED_IN,
            Booking.BookingStatus.CHECKED_OUT,
            Booking.BookingStatus.COMPLETED,
        }:
            raise serializers.ValidationError(
                {'status': 'Setelah CONFIRMED, booking harus berstatus PAID atau CANCELLED terlebih dahulu.'}
            )

        return attrs

    def update(self, instance, validated_data):
        old_snapshot = instance._get_audit_snapshot()
        request = self.context.get('request')
        changed_by = request.user if request and request.user.is_authenticated else None

        update_fields = []

        if 'harga' in validated_data:
            instance.harga = validated_data['harga']
            update_fields.append('harga')

        if 'total_pembayaran' in validated_data:
            instance.total_pembayaran = validated_data['total_pembayaran']
            update_fields.append('total_pembayaran')

        if 'status' in validated_data:
            instance.status = validated_data['status']
            update_fields.append('status')

        if 'cancellation_reason' in validated_data:
            instance.cancellation_reason = validated_data['cancellation_reason']
            update_fields.append('cancellation_reason')

        if update_fields:
            with transaction.atomic():
                instance.save(update_fields=[*update_fields, 'updated_at'])
                instance.create_change_logs_from_snapshot(old_snapshot, changed_by=changed_by)
            
            # Post-save trigger for COMPLETED
            # Check old_snapshot to avoid double trigger if it was already COMPLETED
            if 'status' in validated_data and validated_data['status'] == Booking.BookingStatus.COMPLETED:
                if old_snapshot.get('status') != Booking.BookingStatus.COMPLETED:
                    from inventory.services import record_supply_usage_for_completed_booking
                    record_supply_usage_for_completed_booking(instance)

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
        old_status = instance.status
        instance.update_status(validated_data['status'], changed_by=changed_by)
        
        if validated_data['status'] == Booking.BookingStatus.COMPLETED and old_status != Booking.BookingStatus.COMPLETED:
            from inventory.services import record_supply_usage_for_completed_booking
            record_supply_usage_for_completed_booking(instance)
            
        return instance


class BookingAssignTherapistSerializer(serializers.ModelSerializer):
    """Serializer for assigning/reassigning therapist in PAID or ASSIGNED status."""

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
            Booking.BookingStatus.PAID,
            Booking.BookingStatus.ASSIGNED,
        ]
        if booking.status not in allowed_statuses:
            raise serializers.ValidationError(
                {'status': 'Therapist hanya dapat di-assign/reassign ketika booking berstatus PAID atau ASSIGNED.'}
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
