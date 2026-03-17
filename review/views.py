from datetime import datetime

from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import Booking
from .models import Review
from .permissions import IsSupervisorOrOwner
from .serializers import ReviewContextSerializer, ReviewCreateSerializer, ReviewListSerializer


# ──────────────────────────────────────────────────────────────────
# CREATE  –  POST /api/reviews/
# ──────────────────────────────────────────────────────────────────

class ReviewCollectionView(APIView):
    """
    Review collection endpoint.

    GET /api/reviews/
      - Only OWNER and SUPERVISOR may access.
      - Optional filters:
        - therapistId=<therapist_id>
        - startDate=YYYY-MM-DD
        - endDate=YYYY-MM-DD

    POST /api/reviews/
      - Public QR-token based review creation.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsSupervisorOrOwner()]
        return [permissions.AllowAny()]

    def get(self, request):
        qs = Review.objects.select_related("booking", "therapist", "customer")

        therapist_id = request.query_params.get("therapistId")
        if therapist_id:
            if not therapist_id.isdigit():
                return Response(
                    {"error": "Parameter therapistId harus berupa angka."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(therapist_id=int(therapist_id))

        start_date_raw = request.query_params.get("startDate")
        end_date_raw = request.query_params.get("endDate")

        start_date = None
        end_date = None

        if start_date_raw:
            try:
                start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Format startDate tidak valid. Gunakan YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_raw:
            try:
                end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Format endDate tidak valid. Gunakan YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if start_date and end_date and start_date > end_date:
            return Response(
                {"error": "startDate tidak boleh lebih besar dari endDate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)

        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

        serializer = ReviewListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
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

        serializer = ReviewCreateSerializer(
            data=request.data,
            context={"request": request, "booking": booking},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

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
# DETAIL  –  GET /api/reviews/<pk>/
# ──────────────────────────────────────────────────────────────────

class ReviewDetailView(generics.RetrieveAPIView):
    """Retrieve a single review by its primary key."""

    queryset = Review.objects.select_related("booking", "therapist", "customer")
    serializer_class = ReviewListSerializer
    permission_classes = [IsAuthenticated, IsSupervisorOrOwner]
