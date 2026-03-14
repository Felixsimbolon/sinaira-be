from django.urls import path
from .views import (
    BookingCreateView,
    CustomerBookingHistoryView,
    CheckPhoneNumberView,
    AdminBookingListView,
    AdminBookingDetailView,
    AdminBookingReviewLinkView,
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
    
    # Get/Update booking detail by booking_id (GET, PUT, PATCH)
    path('admin/bookings/<str:booking_id>/', AdminBookingDetailView.as_view(), name='admin-booking-detail'),

    # Generate/get review link token for completed booking (POST)
    path('admin/bookings/<str:booking_id>/review-link/', AdminBookingReviewLinkView.as_view(), name='admin-booking-review-link'),
]
