from django.urls import path
from .views import (
    BookingCreateView,
    CustomerBookingHistoryView,
    CheckPhoneNumberView,
    AdminBookingListView,
    AdminBookingDetailView,
    AdminBookingStatusUpdateView,
    AdminAssignTherapistView,
    AdminBookingGeocodeView,
    AdminBookingTherapistsByDistanceView,
    AdminBookingDetailGeocodeView,
    TherapistBookingStatusUpdateView,
    ParseWhatsAppMessageView,
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
    
    # Get/Update booking detail by booking_id (GET, PUT, PATCH)
    path('admin/bookings/<str:booking_id>/', AdminBookingDetailView.as_view(), name='admin-booking-detail'),

    # Update booking status by booking_id (PATCH)
    path('admin/bookings/<str:booking_id>/status/', AdminBookingStatusUpdateView.as_view(), name='admin-booking-status-update'),

    # Assign therapist by booking_id (PATCH)
    path('admin/bookings/<str:booking_id>/assign-therapist/', AdminAssignTherapistView.as_view(), name='admin-booking-assign-therapist'),

    # List assignable therapists sorted by distance for a booking (GET)
    path('admin/bookings/<str:booking_id>/therapists-by-distance/', AdminBookingTherapistsByDistanceView.as_view(), name='admin-booking-therapists-by-distance'),

    # Therapist updates own assigned booking status (PATCH)
    path('therapist/bookings/<str:booking_id>/status/', TherapistBookingStatusUpdateView.as_view(), name='therapist-booking-status-update'),

    # ── Utility endpoints ─────────────────────────────────────────
    # Parse a WhatsApp message and return extracted fields (POST) — no DB write
    path('bookings/parse-whatsapp/', ParseWhatsAppMessageView.as_view(), name='parse-whatsapp'),
]
