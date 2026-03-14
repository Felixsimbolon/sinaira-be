from rest_framework import serializers

from booking.models import Booking
from therapist.models import Therapist

from .models import Review


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a Review.

    The client sends:
        - rating    (1-5)
        - comment   (optional)

    Booking and token verification are handled in the view.
    `therapist`, `customer`, `customer_name`, and `customer_phone`
    are derived from the booking context.
    """

    booking_id = serializers.CharField(source="booking.booking_id", read_only=True)
    therapist_name = serializers.CharField(source="therapist.name", read_only=True)
    customer_name = serializers.CharField(read_only=True)
    customer_phone = serializers.CharField(read_only=True)

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
            "customer_phone",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "booking",
            "booking_id",
            "therapist",
            "therapist_name",
            "customer",
            "customer_name",
            "customer_phone",
            "created_at",
        ]

    def validate_rating(self, value: int) -> int:
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating harus antara 1 sampai 5."
            )
        return value

    # ── Object creation ───────────────────────────────────────────

    def create(self, validated_data):
        booking: Booking = self.context["booking"]
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

        validated_data["booking"] = booking
        validated_data["therapist"] = therapist
        validated_data["customer"] = request.user if request.user.is_authenticated else None
        validated_data["customer_name"] = booking.nama
        validated_data["customer_phone"] = booking.no_hp

        return super().create(validated_data)


class ReviewListSerializer(serializers.ModelSerializer):
    """Read-only serializer used for listing / detail views."""

    booking_id = serializers.CharField(source="booking.booking_id", read_only=True)
    therapist_name = serializers.CharField(source="therapist.name", read_only=True)
    customer_name = serializers.SerializerMethodField()

    def get_customer_name(self, obj: Review) -> str:
        if obj.customer_name:
            return obj.customer_name
        if obj.customer:
            return obj.customer.name
        return ""

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
            "customer_phone",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReviewContextSerializer(serializers.ModelSerializer):
    """Serializer for opening review form from QR token."""

    booking_id = serializers.CharField(source="booking_id", read_only=True)
    therapist_name = serializers.CharField(source="therapist.name", read_only=True)
    therapist_username = serializers.CharField(source="therapist.username", read_only=True)
    has_review = serializers.SerializerMethodField()
    existing_review = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "booking_id",
            "nama",
            "no_hp",
            "status",
            "tgl_treatment",
            "jam_treatment",
            "perawatan_pilihan",
            "therapist_name",
            "therapist_username",
            "has_review",
            "existing_review",
        ]

    def get_has_review(self, obj: Booking) -> bool:
        return hasattr(obj, "review")

    def get_existing_review(self, obj: Booking):
        if not hasattr(obj, "review"):
            return None
        return ReviewListSerializer(obj.review).data
