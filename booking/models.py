from django.db import models
from django.conf import settings
import random
import string


def generate_booking_id():
    """Generate a unique 6-digit alphanumeric booking ID."""
    while True:
        # Generate 6 random characters (uppercase letters and digits)
        booking_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # Check if this ID already exists (with exception handling for migrations)
        try:
            if not Booking.objects.filter(booking_id=booking_id).exists():
                return booking_id
        except Exception:
            # During migrations, the column might not exist yet
            # In that case, just return the generated ID
            return booking_id


class Booking(models.Model):
    """
    Booking model for customer treatment appointments.
    Supports both anonymous and authenticated bookings.
    """

    class AromatherapyChoice(models.TextChoices):
        JASMINE = "JASMINE", "Jasmine"
        LAVENDER = "LAVENDER", "Lavender"
        ROSE = "ROSE", "Rose"
        SANDALWOOD = "SANDALWOOD", "Sandalwood"

    class BookingStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        ASSIGNED = "ASSIGNED", "Assigned"
        CHECKED_IN = "CHECKED_IN", "Checked-in"
        CHECKED_OUT = "CHECKED_OUT", "Checked-out"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    VALID_STATUS_TRANSITIONS = {
        BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
        BookingStatus.CONFIRMED: {BookingStatus.ASSIGNED, BookingStatus.CANCELLED},
        BookingStatus.ASSIGNED: {BookingStatus.CHECKED_IN, BookingStatus.CANCELLED},
        BookingStatus.CHECKED_IN: {BookingStatus.CHECKED_OUT},
        BookingStatus.CHECKED_OUT: {BookingStatus.COMPLETED},
        BookingStatus.CANCELLED: set(),
        BookingStatus.COMPLETED: set(),
    }

    # Unique 6-digit alphanumeric booking ID
    booking_id = models.CharField(
        max_length=6,
        unique=True,
        default=generate_booking_id,
        editable=False,
        help_text="6-digit alphanumeric booking ID"
    )

    # Link to user account (optional - for booking history)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Optional: linked user account for booking history"
    )

    # Assigned therapist (optional)
    therapist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_bookings",
        limit_choices_to={'role': 'THERAPIST'},
        help_text="Assigned therapist for this booking"
    )

    # Customer information (required regardless of account)
    nama = models.CharField(
        max_length=255,
        help_text="Customer name"
    )
    
    alamat = models.TextField(
        help_text="Customer address"
    )
    
    kota = models.CharField(
        max_length=100,
        help_text="City"
    )
    
    no_hp = models.CharField(
        max_length=20,
        help_text="Phone number",
        db_index=True  # Index for quick lookups
    )

    # Treatment details
    tgl_treatment = models.DateField(
        help_text="Treatment date"
    )
    
    jam_treatment = models.TimeField(
        help_text="Treatment time"
    )
    
    perawatan_pilihan = models.CharField(
        max_length=255,
        help_text="Selected treatment/service"
    )
    
    aromatherapy_oil = models.CharField(
        max_length=20,
        choices=AromatherapyChoice.choices,
        help_text="Selected aromatherapy oil"
    )

    # Medical/Special conditions
    kondisi_khusus = models.TextField(
        blank=True,
        help_text="Special conditions: Pregnant/Post-partum/Menstruation/Medical conditions"
    )

    # Marketing
    tahu_dari = models.CharField(
        max_length=255,
        blank=True,
        help_text="How did you hear about Sènaira"
    )

    # Admin notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes (visible to staff only)"
    )

    voucher_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Applied voucher code for this booking"
    )

    # Booking metadata
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        help_text="Booking status"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tgl_treatment', '-jam_treatment']
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['-tgl_treatment', '-jam_treatment']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.booking_id} - {self.nama} - {self.tgl_treatment}"

    def can_transition_to(self, new_status: str) -> bool:
        """Return True when transition from current status to new_status is allowed."""
        allowed_statuses = self.VALID_STATUS_TRANSITIONS.get(self.status, set())
        return new_status in allowed_statuses

    def update_status(self, new_status: str):
        """Update booking status when transition is valid."""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Status transition from {self.status} to {new_status} is not allowed."
            )

        self.status = new_status
        self.save(update_fields=["status", "updated_at"])

    def assign_therapist(self, therapist):
        """Assign therapist and move status to ASSIGNED when allowed."""
        if self.status != self.BookingStatus.CONFIRMED:
            raise ValueError("Therapist can only be assigned when booking is CONFIRMED.")

        self.therapist = therapist
        self.status = self.BookingStatus.ASSIGNED
        self.save(update_fields=["therapist", "status", "updated_at"])
