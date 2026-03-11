from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Review
from .permissions import IsAuthenticatedUser
from .serializers import ReviewCreateSerializer, ReviewListSerializer


# ──────────────────────────────────────────────────────────────────
# CREATE  –  POST /api/reviews/
# ──────────────────────────────────────────────────────────────────

class ReviewCreateView(generics.CreateAPIView):
    """
    Create a therapist review for a completed booking.

    - Only **authenticated** users may access this endpoint (401 otherwise).
    - The booking must be in COMPLETED status.
    - The booking must belong to the requesting user.
    - Each booking can only be reviewed once.
    - `therapist` and `customer` are set automatically.
    """

    queryset = Review.objects.all()
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticatedUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return created review with the list serializer for richer data.
        output = ReviewListSerializer(serializer.instance).data
        return Response(
            {"message": "Review berhasil dibuat.", "data": output},
            status=status.HTTP_201_CREATED,
        )


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
