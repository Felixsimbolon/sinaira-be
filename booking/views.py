from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, DateFilter
from django.db.models import Q, F, Value
from django.db.models.functions import Replace
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    BookingHistorySerializer,
    BookingStatusUpdateSerializer,
    TherapistBookingStatusUpdateSerializer,
    TherapistBookingListSerializer,
    BookingAssignTherapistSerializer,
    BookingGeocodeSerializer,
    BookingChangeLogSerializer,
)
from .permissions import IsAdminOrSupervisorOrOwner, IsTherapist
from .utils import (
    extract_booking_from_whatsapp_message,
    geocode_location_from_address,
    get_assignable_therapists_by_distance,
)


class AllowAnyPermission(permissions.BasePermission):
    """
    Custom permission that allows anyone (authenticated or anonymous) to access.
    """
    def has_permission(self, request, view):
        return True


class BookingFilter(FilterSet):
    """Custom filter for bookings."""
    status = CharFilter(field_name='status', lookup_expr='iexact')
    kota = CharFilter(field_name='kota', lookup_expr='iexact')
    tgl_treatment = DateFilter(field_name='tgl_treatment')
    tgl_treatment_from = DateFilter(field_name='tgl_treatment', lookup_expr='gte')
    tgl_treatment_to = DateFilter(field_name='tgl_treatment', lookup_expr='lte')

    class Meta:
        model = Booking
        fields = ['status', 'kota', 'tgl_treatment', 'tgl_treatment_from', 'tgl_treatment_to']


# ──────────────────────────────────────────────────────────────────
# CUSTOMER VIEWS (Public)
# ──────────────────────────────────────────────────────────────────

class BookingCreateView(generics.CreateAPIView):
    """
    Create a new booking.
    Accessible to anyone (anonymous or authenticated customers).
    """
    queryset = Booking.objects.all()
    serializer_class = BookingCreateSerializer
    permission_classes = [AllowAnyPermission]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                'message': 'Booking created successfully',
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )


class CustomerBookingHistoryView(generics.ListAPIView):
    """
    View booking history for authenticated customers.
    Returns bookings associated with the customer's phone number.
    """
    serializer_class = BookingHistorySerializer
    permission_classes = [AllowAnyPermission]

    def get_queryset(self):
        # Get bookings by phone number (from query param)
        no_hp = self.request.query_params.get('no_hp', None)
        
        if no_hp:
            return Booking.objects.filter(no_hp=no_hp)
        
        # If user is authenticated, show their bookings
        if self.request.user.is_authenticated:
            return Booking.objects.filter(user=self.request.user)
        
        return Booking.objects.none()


class CheckPhoneNumberView(APIView):
    """
    Check if a phone number has existing bookings.
    Returns booking count for the phone number.
    """
    permission_classes = [AllowAnyPermission]
    
    @staticmethod
    def _digits_only(value: str) -> str:
        return ''.join(ch for ch in value if ch.isdigit())
    
    def _phone_candidates(self, raw_phone: str) -> set[str]:
        """Build equivalent phone candidates for 08.. and 62.. formats."""
        digits = self._digits_only(raw_phone)
        candidates = {digits}
        
        if digits.startswith('0') and len(digits) > 1:
            candidates.add(f"62{digits[1:]}")
        elif digits.startswith('62') and len(digits) > 2:
            candidates.add(f"0{digits[2:]}")
        
        return {item for item in candidates if item}

    def get(self, request):
        no_hp = request.query_params.get('no_hp', None)
        
        if not no_hp:
            return Response(
                {'error': 'no_hp parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        phone_candidates = self._phone_candidates(no_hp)

        normalized_no_hp = Replace(
            Replace(
                Replace(
                    Replace(
                        Replace(F('no_hp'), Value(' '), Value('')),
                        Value('-'),
                        Value(''),
                    ),
                    Value('+'),
                    Value(''),
                ),
                Value('('),
                Value(''),
            ),
            Value(')'),
            Value(''),
        )

        base_qs = (
            Booking.objects
            .annotate(normalized_phone=normalized_no_hp)
            .filter(normalized_phone__in=phone_candidates)
        )

        bookings_count = base_qs.count()
        
        # Hanya hitung yang COMPLETED untuk loyalty voucher
        completed_bookings_count = base_qs.filter(
            status=Booking.BookingStatus.COMPLETED
        ).count()
        
        return Response({
            'no_hp': self._digits_only(no_hp),
            'has_bookings': bookings_count > 0,
            'bookings_count': bookings_count,
            'completed_bookings_count': completed_bookings_count,
        })

# ──────────────────────────────────────────────────────────────────
# ADMIN VIEWS (Staff Only: Owner, Supervisor, Admin)
# ──────────────────────────────────────────────────────────────────

class AdminBookingListView(generics.ListAPIView):
    """
    Admin view for listing all bookings.
    
    Features:
    - Search by name or phone number
    - Filter by status and date
    - Sorting by any field
    
    Only accessible to: OWNER, SUPERVISOR, ADMIN
    """
    queryset = Booking.objects.select_related('review').all()
    serializer_class = BookingListSerializer
    permission_classes = [IsAdminOrSupervisorOrOwner]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BookingFilter
    search_fields = ['nama', 'no_hp', 'booking_id']
    ordering_fields = ['booking_id', 'nama', 'tgl_treatment', 'jam_treatment', 'status', 'created_at']
    ordering = ['-created_at']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })


class AdminBookingDetailView(generics.RetrieveUpdateAPIView):
    """
    Admin view for viewing and updating booking details.
    
    Returns complete booking information including:
    - Customer information
    - Service details
    - Schedule
    - Status
    - Assigned therapist (if any)
    - Internal notes
    
    Only accessible to: OWNER, SUPERVISOR, ADMIN
    """
    queryset = Booking.objects.all()
    serializer_class = BookingDetailSerializer
    permission_classes = [IsAdminOrSupervisorOrOwner]
    lookup_field = 'booking_id'

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {kwargs.get("booking_id")} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )


class AdminBookingReviewLinkView(APIView):
    """
    Generate (or return existing) review link token for a COMPLETED booking.
    Only accessible to: OWNER, SUPERVISOR, ADMIN.
    """
    permission_classes = [IsAdminOrSupervisorOrOwner]

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, booking_id=booking_id)

        if booking.status != Booking.BookingStatus.COMPLETED:
            return Response(
                {
                    'error': 'Booking belum selesai',
                    'detail': 'QR review hanya dapat dibuat untuk booking berstatus COMPLETED.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if booking.therapist is None:
            return Response(
                {
                    'error': 'Therapist belum ditugaskan',
                    'detail': 'Booking harus memiliki therapist sebelum link review dibuat.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not booking.review_token:
            booking.generate_review_token(save=True)

        review_url = f"{settings.REVIEW_FORM_BASE_URL}?token={booking.review_token}"

        return Response(
            {
                'booking_id': booking.booking_id,
                'customer_name': booking.nama,
                'customer_phone': booking.no_hp,
                'therapist_name': booking.therapist.name,
                'status': booking.status,
                'has_review': hasattr(booking, 'review'),
                'review_token': booking.review_token,
                'review_url': review_url,
            }
        )

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            if instance.status != Booking.BookingStatus.PENDING:
                return Response(
                    {
                        'error': 'Booking hanya dapat di-update penuh ketika status masih PENDING.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if any(field in request.data for field in ['status', 'therapist', 'therapist_id']):
                return Response(
                    {
                        'error': 'Update status atau therapist harus menggunakan endpoint khusus.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            return Response({
                'message': 'Booking updated successfully',
                'data': serializer.data
            })
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {kwargs.get("booking_id")} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )


class AdminBookingReviewLinkView(APIView):
    """
    Generate (or return existing) review link token for a COMPLETED booking.
    Only accessible to: OWNER, SUPERVISOR, ADMIN.
    """
    permission_classes = [IsAdminOrSupervisorOrOwner]

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, booking_id=booking_id)

        if booking.status != Booking.BookingStatus.COMPLETED:
            return Response(
                {
                    'error': 'Booking belum selesai',
                    'detail': 'QR review hanya dapat dibuat untuk booking berstatus COMPLETED.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if booking.therapist is None:
            return Response(
                {
                    'error': 'Therapist belum ditugaskan',
                    'detail': 'Booking harus memiliki therapist sebelum link review dibuat.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not booking.review_token:
            booking.generate_review_token(save=True)

        review_url = f"{settings.REVIEW_FORM_BASE_URL}?token={booking.review_token}"

        return Response(
            {
                'booking_id': booking.booking_id,
                'customer_name': booking.nama,
                'customer_phone': booking.no_hp,
                'therapist_name': booking.therapist.name,
                'status': booking.status,
                'has_review': hasattr(booking, 'review'),
                'review_token': booking.review_token,
                'review_url': review_url,
            }
        )

class AdminBookingStatusUpdateView(APIView):
    """Admin endpoint for updating booking status with transition validation."""

    permission_classes = [IsAdminOrSupervisorOrOwner]

    def patch(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BookingStatusUpdateSerializer(
            booking,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Booking status updated successfully',
                'data': {
                    'booking_id': booking.booking_id,
                    'status': booking.status,
                }
            },
            status=status.HTTP_200_OK
        )


class AdminAssignTherapistView(APIView):
    """Admin endpoint for assigning therapist and setting booking status to ASSIGNED."""

    permission_classes = [IsAdminOrSupervisorOrOwner]

    def patch(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BookingAssignTherapistSerializer(
            booking,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Therapist assigned successfully',
                'data': {
                    'booking_id': booking.booking_id,
                    'status': booking.status,
                    'therapist': serializer.data.get('therapist'),
                }
            },
            status=status.HTTP_200_OK
        )


class AdminBookingGeocodeView(APIView):
    """Admin endpoint for geocoding booking-related address fields."""

    permission_classes = [IsAdminOrSupervisorOrOwner]

    def post(self, request):
        serializer = BookingGeocodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        latitude, longitude = geocode_location_from_address(
            alamat=serializer.validated_data.get('alamat', ''),
            kelurahan=serializer.validated_data.get('kelurahan', ''),
            kecamatan=serializer.validated_data.get('kecamatan', ''),
            kota=serializer.validated_data.get('kota', ''),
        )

        if latitude is None or longitude is None:
            return Response(
                {
                    'error': 'Koordinat tidak ditemukan dari alamat yang diberikan.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                'message': 'Geocoding success',
                'data': {
                    'latitude': latitude,
                    'longitude': longitude,
                }
            },
            status=status.HTTP_200_OK
        )


class AdminBookingTherapistsByDistanceView(APIView):
    """Admin endpoint for listing assignable therapists sorted by distance."""

    permission_classes = [IsAdminOrSupervisorOrOwner]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            therapists = get_assignable_therapists_by_distance(booking)
        except ValueError as error:
            return Response(
                {
                    'error': str(error)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                'message': 'Therapists retrieved successfully',
                'data': {
                    'booking_id': booking.booking_id,
                    'results': therapists,
                }
            },
            status=status.HTTP_200_OK
        )


class AdminBookingDetailGeocodeView(APIView):
    """Admin endpoint for manually re-geocoding a booking by booking_id."""

    permission_classes = [IsAdminOrSupervisorOrOwner]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        latitude, longitude = geocode_location_from_address(
            alamat=booking.alamat or '',
            kelurahan=booking.kelurahan or '',
            kecamatan=booking.kecamatan or '',
            kota=booking.kota or '',
        )

        if latitude is None or longitude is None:
            return Response(
                {
                    'error': 'Koordinat tidak ditemukan untuk booking ini.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        old_snapshot = booking._get_audit_snapshot()
        booking.latitude = latitude
        booking.longitude = longitude
        booking.save(update_fields=['latitude', 'longitude', 'updated_at'])
        booking.create_change_logs_from_snapshot(old_snapshot, changed_by=request.user)

        return Response(
            {
                'message': 'Booking geocode updated successfully',
                'data': {
                    'booking_id': booking.booking_id,
                    'latitude': booking.latitude,
                    'longitude': booking.longitude,
                }
            },
            status=status.HTTP_200_OK
        )


class AdminBookingChangeLogListView(APIView):
    """Admin endpoint for viewing booking field-level change logs."""

    permission_classes = [IsAdminOrSupervisorOrOwner]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        logs = booking.change_logs.all()
        serializer = BookingChangeLogSerializer(logs, many=True)
        return Response(
            {
                'count': logs.count(),
                'results': serializer.data,
            },
            status=status.HTTP_200_OK
        )


class TherapistBookingListView(generics.ListAPIView):
    """
    Therapist endpoint for listing their assigned bookings (Sesi Saya).
    Returns only bookings where therapist = request.user.
    """
    permission_classes = [IsTherapist]
    serializer_class = TherapistBookingListSerializer
    pagination_class = None

    def get_queryset(self):
        return Booking.objects.filter(therapist=self.request.user).order_by(
            '-tgl_treatment', '-jam_treatment'
        )


class AdminTherapistAssignedBookingsView(generics.ListAPIView):
    """
    Admin endpoint to list all bookings assigned to a specific therapist.
    Uses the same shape as therapist Sesi Saya, but filtered by therapist_id.
    """

    permission_classes = [IsAdminOrSupervisorOrOwner]
    serializer_class = TherapistBookingListSerializer
    pagination_class = None

    def get_queryset(self):
        from therapist.models import Therapist  # local import to avoid circular

        therapist_id = self.kwargs.get('id')
        try:
            therapist = Therapist.objects.get(id=therapist_id)
        except Therapist.DoesNotExist:
            return Booking.objects.none()

        if not therapist.user:
            return Booking.objects.none()

        return Booking.objects.filter(therapist=therapist.user).order_by(
            '-tgl_treatment', '-jam_treatment'
        )


class TherapistBookingDetailView(APIView):
    """
    Therapist endpoint for retrieving one assigned booking detail.
    Returns 404 if booking is not assigned to the current therapist.
    """
    permission_classes = [IsTherapist]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.',
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if booking.therapist_id != request.user.id:
            return Response(
                {
                    'error': 'Anda tidak memiliki akses ke booking ini.',
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BookingDetailSerializer(booking)
        return Response(serializer.data)


class TherapistBookingStatusUpdateView(APIView):
    """Therapist endpoint for updating CHECKED_IN and CHECKED_OUT status."""

    permission_classes = [IsTherapist]

    def patch(self, request, booking_id):
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {
                    'error': 'Booking tidak ditemukan',
                    'detail': f'Booking dengan ID {booking_id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if booking.therapist_id and booking.therapist_id != request.user.id:
            return Response(
                {
                    'error': 'Anda tidak memiliki akses untuk mengubah status booking ini.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = TherapistBookingStatusUpdateSerializer(
            booking,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Booking status updated successfully',
                'data': {
                    'booking_id': booking.booking_id,
                    'status': booking.status,
                }
            },
            status=status.HTTP_200_OK
        )


# ──────────────────────────────────────────────────────────────────
# UTILITY VIEWS
# ──────────────────────────────────────────────────────────────────

class ParseWhatsAppMessageView(APIView):
    """
    Parse a WhatsApp reservation message and return extracted booking fields.

    Does NOT create a booking or touch the database — purely for data extraction.

    Request body (JSON):
        { "message": "<raw WhatsApp text>" }

    Response (200):
        {
            "nama": "",
            "alamat": "",
            "kota": "",
            "no_hp": "",
            "tgl_treatment": "",
            "jam_treatment": "",
            "perawatan_pilihan": "",
            "aromatherapy_oil": "",
            "kondisi_khusus": "",
            "tahu_dari": ""
        }

    Accessible to anyone (public endpoint, no sensitive data is stored).
    """
    permission_classes = [AllowAnyPermission]

    def post(self, request):
        message = request.data.get('message', '')
        if not message or not isinstance(message, str):
            return Response(
                {'error': 'Field "message" wajib diisi dan harus berupa string.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        extracted = extract_booking_from_whatsapp_message(message)
        return Response(extracted, status=status.HTTP_200_OK)
