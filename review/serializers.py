from rest_framework import serializers

from booking.models import Booking
from therapist.models import Therapist

from .models import Review


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a Review.

    The client sends:
        - booking   (booking PK)
        - rating    (1-5)
        - comment   (optional)

    `therapist` and `customer` are set automatically from the booking
    and the authenticated user.
    """

    class Meta:
        model = Review
        fields = [
            "id",
            "booking",
            "therapist",
            "customer",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "therapist", "customer", "created_at"]

    # ── Custom validation ─────────────────────────────────────────

    def validate_booking(self, value: Booking) -> Booking:
        """Ensure the booking is COMPLETED and belongs to the current user."""
        request = self.context["request"]

        if value.status != Booking.BookingStatus.COMPLETED:
            raise serializers.ValidationError(
                "Review hanya dapat diberikan untuk booking yang sudah selesai (COMPLETED)."
            )

        if value.user != request.user:
            raise serializers.ValidationError(
                "Anda hanya dapat mereview booking milik Anda sendiri."
            )

        if hasattr(value, "review"):
            raise serializers.ValidationError(
                "Booking ini sudah memiliki review."
            )

        return value

    def validate_rating(self, value: int) -> int:
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating harus antara 1 sampai 5."
            )
        return value

    # ── Object creation ───────────────────────────────────────────

    def create(self, validated_data):
        booking: Booking = validated_data["booking"]
        request = self.context["request"]

        # Resolve the Therapist profile from the booking's assigned
        # therapist user (AUTH_USER_MODEL) via username lookup.
        therapist_user = booking.therapist
        if therapist_user is None:
            raise serializers.ValidationError(
                {"booking": "Booking ini belum memiliki therapist yang ditugaskan."}
            )

        try:
            therapist = Therapist.objects.get(username=therapist_user.username)
        except Therapist.DoesNotExist:
            raise serializers.ValidationError(
                {"booking": "Profil therapist tidak ditemukan."}
            )

        validated_data["therapist"] = therapist
        validated_data["customer"] = request.user

        return super().create(validated_data)


class ReviewListSerializer(serializers.ModelSerializer):
    """Read-only serializer used for listing / detail views."""

    booking_id = serializers.CharField(source="booking.booking_id", read_only=True)
    therapist_name = serializers.CharField(source="therapist.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "booking",
            "booking_id",
            "therapist",
            "therapist_name",
            "customer",
            "customer_name",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
