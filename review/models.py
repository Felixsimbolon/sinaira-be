from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """
    Therapist review linked to a completed Booking.

    Constraints
    -----------
    - Each booking can only have **one** review  (OneToOneField).
    - Rating is an integer between 1 and 5.
    - Comment is optional.
    """

    booking = models.OneToOneField(
        "booking.Booking",
        on_delete=models.CASCADE,
        related_name="review",
        help_text="The booking this review belongs to.",
    )

    therapist = models.ForeignKey(
        "therapist.Therapist",
        on_delete=models.CASCADE,
        related_name="reviews",
        help_text="The therapist being reviewed.",
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviews",
        null=True,
        blank=True,
        help_text="The customer who wrote the review.",
    )

    customer_name = models.CharField(
        max_length=255,
        default="",
        help_text="Customer display name captured from booking data.",
    )

    customer_phone = models.CharField(
        max_length=20,
        default="",
        db_index=True,
        help_text="Customer phone number captured from booking data.",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (worst) to 5 (best).",
    )

    comment = models.TextField(
        blank=True,
        default="",
        help_text="Optional review comment.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking"],
                name="unique_review_per_booking",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Review #{self.pk} — Booking {self.booking.booking_id} "
            f"— {self.rating}/5"
        )
