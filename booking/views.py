from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, DateFilter
from django.db.models import Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    BookingHistorySerializer
)
from .permissions import IsAdminOrSupervisorOrOwner


class AllowAnyPermission(permissions.BasePermission):
    """
    Custom permission that allows anyone (authenticated or anonymous) to access.
    """
    def has_permission(self, request, view):
        return True


class BookingFilter(FilterSet):
    """Custom filter for bookings."""
    status = CharFilter(field_name='status', lookup_expr='iexact')
    tgl_treatment = DateFilter(field_name='tgl_treatment')
    tgl_treatment_from = DateFilter(field_name='tgl_treatment', lookup_expr='gte')
    tgl_treatment_to = DateFilter(field_name='tgl_treatment', lookup_expr='lte')

    class Meta:
        model = Booking
        fields = ['status', 'tgl_treatment', 'tgl_treatment_from', 'tgl_treatment_to']


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

    def get(self, request):
        no_hp = request.query_params.get('no_hp', None)
        
        if not no_hp:
            return Response(
                {'error': 'no_hp parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bookings_count = Booking.objects.filter(no_hp=no_hp).count()
        
        return Response({
            'no_hp': no_hp,
            'has_bookings': bookings_count > 0,
            'bookings_count': bookings_count
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
    ordering = ['-tgl_treatment', '-jam_treatment']

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
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
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

