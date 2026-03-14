from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import Booking
from .models import Review
from .serializers import ReviewContextSerializer, ReviewCreateSerializer, ReviewListSerializer


# ──────────────────────────────────────────────────────────────────
# CREATE  –  POST /api/reviews/
# ──────────────────────────────────────────────────────────────────

class ReviewCreateView(generics.CreateAPIView):
    """
    Create a therapist review for a completed booking.

    - Accepts anonymous customers via review token from QR code.
    - Authenticated staff users are blocked.
    - The booking must be in COMPLETED status.
    - Each booking can only be reviewed once.
    - `therapist`, `customer_name`, and `customer_phone` are set automatically.
    """

    queryset = Review.objects.all()
    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        booking_id = request.data.get("booking_id")
        review_token = request.data.get("review_token")

        if request.user and request.user.is_authenticated and hasattr(request.user, "role"):
            return Response(
                {"error": "Role ini tidak diperbolehkan membuat review customer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not review_token:
            return Response(
                {"error": "Token review tidak valid atau tidak tersedia."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not booking_id:
            return Response(
                {"error": "booking_id wajib diisi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = Booking.objects.select_related("therapist").filter(booking_id=booking_id).first()
        if booking is None:
            return Response(
                {"error": "Booking tidak ditemukan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.review_token != review_token:
            return Response(
                {"error": "Token review tidak valid atau sudah kedaluwarsa."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if booking.status != Booking.BookingStatus.COMPLETED:
            return Response(
                {
                    "error": "Review hanya dapat diberikan untuk booking yang sudah selesai (COMPLETED)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(booking, "review"):
            return Response(
                {"error": "Booking ini sudah memiliki review."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data, context={**self.get_serializer_context(), "booking": booking})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return created review with the list serializer for richer data.
        output = ReviewListSerializer(serializer.instance).data
        return Response(
            {"message": "Review berhasil dibuat.", "data": output},
            status=status.HTTP_201_CREATED,
        )


class ReviewContextView(APIView):
    """
    Resolve booking context for a QR review link.

    GET /api/reviews/context/?token=<review_token>
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get("token")

        if not token:
            return Response(
                {"error": "token query parameter wajib diisi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = Booking.objects.select_related("therapist").filter(review_token=token).first()
        if booking is None:
            return Response(
                {"error": "Token review tidak valid atau sudah kedaluwarsa."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if booking.status != Booking.BookingStatus.COMPLETED:
            return Response(
                {
                    "error": "Review belum tersedia karena sesi belum berstatus COMPLETED."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.therapist is None:
            return Response(
                {"error": "Booking belum memiliki therapist yang ditugaskan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReviewContextSerializer(booking)
        return Response(serializer.data)


# ──────────────────────────────────────────────────────────────────
# LIST  –  GET /api/reviews/
# ──────────────────────────────────────────────────────────────────

class ReviewListView(generics.ListAPIView):
    """
    List all reviews.  Supports optional query-param filters:
        ?therapist=<therapist_pk>
        ?customer=<user_pk>
        ?booking=<booking_pk>
    """

    serializer_class = ReviewListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Review.objects.select_related("booking", "therapist", "customer")

        therapist_id = self.request.query_params.get("therapist")
        if therapist_id:
            qs = qs.filter(therapist_id=therapist_id)

        customer_id = self.request.query_params.get("customer")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        booking_id = self.request.query_params.get("booking")
        if booking_id:
            qs = qs.filter(booking_id=booking_id)

        return qs


# ──────────────────────────────────────────────────────────────────
# DETAIL  –  GET /api/reviews/<pk>/
# ──────────────────────────────────────────────────────────────────

class ReviewDetailView(generics.RetrieveAPIView):
    """Retrieve a single review by its primary key."""

    queryset = Review.objects.select_related("booking", "therapist", "customer")
    serializer_class = ReviewListSerializer
    permission_classes = [IsAuthenticated]
