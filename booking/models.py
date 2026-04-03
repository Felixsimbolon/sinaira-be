from django.db import connection, models
from django.conf import settings
from django.db import transaction
from datetime import date, datetime, time
import random
import string
import secrets


def _booking_id_column_exists() -> bool:
    try:
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(
                cursor,
                Booking._meta.db_table,
            )
        return any(column.name == "booking_id" for column in description)
    except Exception:
        return False


def generate_booking_id():
    """Generate a unique 6-digit alphanumeric booking ID."""
    while True:
        # Generate 6 random characters (uppercase letters and digits)
        booking_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # During migrations the booking_id column may not exist yet.
        # Avoid querying it until the schema is ready to prevent transaction abort.
        if not _booking_id_column_exists():
            return booking_id

        if not Booking.objects.filter(booking_id=booking_id).exists():
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
        PAID = "PAID", "Paid"
        ASSIGNED = "ASSIGNED", "Assigned"
        CHECKED_IN = "CHECKED_IN", "Checked-in"
        CHECKED_OUT = "CHECKED_OUT", "Checked-out"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    VALID_STATUS_TRANSITIONS = {
        BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
        BookingStatus.CONFIRMED: {BookingStatus.PAID, BookingStatus.CANCELLED},
        BookingStatus.PAID: {BookingStatus.ASSIGNED, BookingStatus.CANCELLED},
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

    kelurahan = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kelurahan"
    )

    kecamatan = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kecamatan"
    )
    
    kota = models.CharField(
        max_length=100,
        help_text="City"
    )

    kode_pos = models.CharField(
        max_length=10,
        blank=True,
        help_text="Postal code"
    )

    latitude = models.FloatField(
        blank=True,
        null=True,
        help_text="Latitude for booking location"
    )

    longitude = models.FloatField(
        blank=True,
        null=True,
        help_text="Longitude for booking location"
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

    harga = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base treatment price before shipping/adjustment"
    )

    total_pembayaran = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final payable amount including shipping/adjustment"
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

    cancellation_reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason required when booking is cancelled"
    )

    voucher_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Applied voucher code for this booking"
    )

    review_token = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Secure token used in QR link for customer review"
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

    def generate_review_token(self, save: bool = True) -> str:
        """Generate a unique token for public review links."""
        while True:
            token = secrets.token_urlsafe(32)
            if not Booking.objects.filter(review_token=token).exists():
                self.review_token = token
                if save:
                    self.save(update_fields=['review_token', 'updated_at'])
                return token
    def _get_audit_snapshot(self) -> dict:
        """Return tracked booking values before mutation."""
        excluded_fields = {'id', 'booking_id', 'created_at', 'updated_at'}
        snapshot = {}

        for field in self._meta.fields:
            if field.name in excluded_fields:
                continue

            attr_name = field.attname if field.is_relation else field.name
            snapshot[field.name] = getattr(self, attr_name)

        return snapshot

    @staticmethod
    def _serialize_audit_value(value):
        if value is None:
            return None
        if isinstance(value, (date, datetime, time)):
            return value.isoformat()
        return str(value)

    def _resolve_fk_display(self, field, pk_value):
        """Return a human-readable string for a FK value instead of a raw ID."""
        if pk_value is None:
            return None
        try:
            related_obj = field.related_model.objects.get(pk=pk_value)
            if hasattr(related_obj, 'name') and related_obj.name:
                return related_obj.name
            return str(related_obj)
        except field.related_model.DoesNotExist:
            return str(pk_value)

    def create_change_logs_from_snapshot(self, old_snapshot: dict, changed_by=None):
        """Persist per-field delta logs from old_snapshot to current state."""
        log_entries = []

        for field_name, old_value in old_snapshot.items():
            field = self._meta.get_field(field_name)
            attr_name = field.attname if field.is_relation else field.name
            new_value = getattr(self, attr_name)

            if old_value == new_value:
                continue

            if field.is_relation:
                display_old = self._resolve_fk_display(field, old_value)
                display_new = self._resolve_fk_display(field, new_value)
            else:
                display_old = self._serialize_audit_value(old_value)
                display_new = self._serialize_audit_value(new_value)

            log_entries.append(
                BookingChangeLog(
                    booking=self,
                    field_name=field_name,
                    old_value=display_old,
                    new_value=display_new,
                    changed_by=changed_by,
                )
            )

        if log_entries:
            BookingChangeLog.objects.bulk_create(log_entries)

    def can_transition_to(self, new_status: str) -> bool:
        """Return True when transition from current status to new_status is allowed."""
        allowed_statuses = self.VALID_STATUS_TRANSITIONS.get(self.status, set())
        return new_status in allowed_statuses

    def update_status(self, new_status: str, changed_by=None):
        """Update booking status when transition is valid."""
        old_snapshot = self._get_audit_snapshot()

        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Status transition from {self.status} to {new_status} is not allowed."
            )

        self.status = new_status
        with transaction.atomic():
            self.save(update_fields=["status", "updated_at"])
            self.create_change_logs_from_snapshot(old_snapshot, changed_by=changed_by)

    def assign_therapist(self, therapist, changed_by=None):
        """Assign or reassign therapist when booking is PAID or ASSIGNED."""
        old_snapshot = self._get_audit_snapshot()

        if self.status not in [self.BookingStatus.PAID, self.BookingStatus.ASSIGNED]:
            raise ValueError("Therapist can only be assigned when booking is PAID or ASSIGNED.")

        self.therapist = therapist
        self.status = self.BookingStatus.ASSIGNED
        with transaction.atomic():
            self.save(update_fields=["therapist", "status", "updated_at"])
            self.create_change_logs_from_snapshot(old_snapshot, changed_by=changed_by)


class BookingChangeLog(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='change_logs',
    )
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_change_logs',
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['booking', '-changed_at']),
            models.Index(fields=['field_name']),
        ]

    def __str__(self):
        return f"{self.booking.booking_id} - {self.field_name}"
