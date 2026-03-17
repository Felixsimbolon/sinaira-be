from django.db.models import Avg, Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import Booking
from review.models import Review

from .permissions import IsSupervisorOrOwner
from .serializers import TherapistPerformanceSummaryQuerySerializer


class TherapistPerformanceSummaryView(APIView):
	"""
	GET /api/dashboard/therapist/performance-summary

	Query params (required):
	- startDate: YYYY-MM-DD
	- endDate: YYYY-MM-DD
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request):
		query_serializer = TherapistPerformanceSummaryQuerySerializer(
			data=request.query_params
		)
		query_serializer.is_valid(raise_exception=True)

		start_date = query_serializer.validated_data["start_date"]
		end_date = query_serializer.validated_data["end_date"]

		bookings = Booking.objects.filter(
			tgl_treatment__gte=start_date,
			tgl_treatment__lte=end_date,
		)

		total_bookings = bookings.count()
		completed_bookings = bookings.filter(
			status=Booking.BookingStatus.COMPLETED
		).count()
		cancelled_bookings = bookings.filter(
			status=Booking.BookingStatus.CANCELLED
		).count()

		review_qs = Review.objects.filter(
			booking__tgl_treatment__gte=start_date,
			booking__tgl_treatment__lte=end_date,
		)
		avg_rating = review_qs.aggregate(avg_rating=Avg("rating"))["avg_rating"]

		therapist_rows = (
			bookings.exclude(therapist__isnull=True)
			.values("therapist_id", "therapist__name")
			.annotate(
				total_bookings=Count("id"),
				completed_bookings=Count(
					"id",
					filter=Q(status=Booking.BookingStatus.COMPLETED),
				),
				cancelled_bookings=Count(
					"id",
					filter=Q(status=Booking.BookingStatus.CANCELLED),
				),
				average_rating=Avg("review__rating"),
			)
			.order_by("therapist__name")
		)

		by_therapist = [
			{
				"therapistId": row["therapist_id"],
				"therapistName": row["therapist__name"] or "-",
				"totalBookings": row["total_bookings"],
				"completedBookings": row["completed_bookings"],
				"cancelledBookings": row["cancelled_bookings"],
				"averageRating": (
					round(float(row["average_rating"]), 2)
					if row["average_rating"] is not None
					else None
				),
			}
			for row in therapist_rows
		]

		payload = {
			"period": {
				"startDate": start_date.isoformat(),
				"endDate": end_date.isoformat(),
			},
			"summary": {
				"totalBookings": total_bookings,
				"completedBookings": completed_bookings,
				"cancelledBookings": cancelled_bookings,
				"averageRating": (
					round(float(avg_rating), 2) if avg_rating is not None else None
				),
			},
			"byTherapist": by_therapist,
		}

		return Response(payload, status=status.HTTP_200_OK)
