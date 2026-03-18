from django.urls import path
from .views import (
    BookingCreateView,
    CustomerBookingHistoryView,
    CheckPhoneNumberView,
    AdminBookingListView,
    AdminBookingDetailView,
<<<<<<< HEAD
<<<<<<< HEAD
    AdminBookingReviewLinkView,
=======
=======
    AdminBookingReviewLinkView,
>>>>>>> a961ee4cc0dd61dc2165ae2d4ed849f14a9b0aa0
    AdminBookingStatusUpdateView,
    AdminAssignTherapistView,
    TherapistBookingListView,
    TherapistBookingDetailView,
    AdminBookingGeocodeView,
    AdminBookingTherapistsByDistanceView,
    AdminBookingDetailGeocodeView,
    AdminBookingChangeLogListView,
    AdminTherapistAssignedBookingsView,
    TherapistBookingStatusUpdateView,
    ParseWhatsAppMessageView,
>>>>>>> 3f5657a8802988de6feacf0c7f21842f72abe0fb
)
app_name = 'booking'

urlpatterns = [
    # ── Customer endpoints (public) ───────────────────────────────
    # Create new booking (POST)
    path('bookings/', BookingCreateView.as_view(), name='booking-create'),
    
    # Check phone number (GET with ?no_hp=xxx)
    path('bookings/check-phone/', CheckPhoneNumberView.as_view(), name='check-phone'),
    
    # Get booking history (GET with ?no_hp=xxx)
    path('bookings/history/', CustomerBookingHistoryView.as_view(), name='booking-history'),
    
    # ── Admin endpoints (staff only) ──────────────────────────────
    # List all bookings with search, filter, sorting (GET)
    path('admin/bookings/', AdminBookingListView.as_view(), name='admin-booking-list'),

    # Geocode booking address fields (POST)
    path('admin/bookings/geocode/', AdminBookingGeocodeView.as_view(), name='admin-booking-geocode'),

    # Re-geocode a booking detail by booking_id (POST)
    path('admin/bookings/<str:booking_id>/geocode/', AdminBookingDetailGeocodeView.as_view(), name='admin-booking-detail-geocode'),

    # Booking change logs by booking_id (GET)
    path('admin/bookings/<str:booking_id>/change-logs/', AdminBookingChangeLogListView.as_view(), name='admin-booking-change-logs'),
    
    # Get/Update booking detail by booking_id (GET, PUT, PATCH)
    path('admin/bookings/<str:booking_id>/', AdminBookingDetailView.as_view(), name='admin-booking-detail'),

    # Generate/get review link token for completed booking (POST)
    path('admin/bookings/<str:booking_id>/review-link/', AdminBookingReviewLinkView.as_view(), name='admin-booking-review-link'),
    # Update booking status by booking_id (PATCH)
    path('admin/bookings/<str:booking_id>/status/', AdminBookingStatusUpdateView.as_view(), name='admin-booking-status-update'),

    # Assign therapist by booking_id (PATCH)
    path('admin/bookings/<str:booking_id>/assign-therapist/', AdminAssignTherapistView.as_view(), name='admin-booking-assign-therapist'),

    # Recommend therapists by distance for a booking (GET)
    path(
        'admin/bookings/<str:booking_id>/therapists-by-distance/',
        AdminBookingTherapistsByDistanceView.as_view(),
        name='admin-booking-therapists-by-distance',
    ),

    # List bookings assigned to a specific therapist (by therapist id, admin only)
    path(
        'admin/therapists/<int:id>/bookings/',
        AdminTherapistAssignedBookingsView.as_view(),
        name='admin-therapist-assigned-bookings',
    ),

    # Therapist: list and detail for assigned bookings (Sesi Saya)
    path('therapist/bookings/', TherapistBookingListView.as_view(), name='therapist-booking-list'),
    path('therapist/bookings/<str:booking_id>/', TherapistBookingDetailView.as_view(), name='therapist-booking-detail'),
    path('therapist/bookings/<str:booking_id>/status/', TherapistBookingStatusUpdateView.as_view(), name='therapist-booking-status-update'),

    # ── Utility endpoints ─────────────────────────────────────────
    # Parse a WhatsApp message and return extracted fields (POST) — no DB write
    path('bookings/parse-whatsapp/', ParseWhatsAppMessageView.as_view(), name='parse-whatsapp'),
]
