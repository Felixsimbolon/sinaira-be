from django.db.models import Avg, Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import Booking
from review.models import Review

from .membership_services import (
    build_cohort_matrix,
    compute_promo_impact,
    find_at_risk_customers,
)
from .permissions import IsSupervisorOrOwner
from .serializers import (
    CohortQuerySerializer,
    GlobalDateFilterSerializer,
    KPIAggregationQuerySerializer,
    PromoImpactQuerySerializer,
    TherapistPerformanceSummaryQuerySerializer,
)
from .services import aggregate_kpi
from .therapist_services import compute_all_therapist_retentions, get_therapist_detail


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

		# AC 17-19: batch-compute clientRetentionRate for each therapist
		therapist_ids = [row["therapist_id"] for row in therapist_rows]
		retention_map = compute_all_therapist_retentions(
			therapist_ids, start_date, end_date
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
				"clientRetentionRate": retention_map.get(row["therapist_id"]),
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


class KPIAggregationView(APIView):
	"""
	GET /api/dashboard/kpi

	Executive KPI dashboard – returns revenue series, booking-count series,
	comparison data, promo annotations, and optional moving-average series.

	Query params
	------------
	startDate          : str   (required)  YYYY-MM-DD
	endDate            : str   (required)  YYYY-MM-DD
	groupBy            : str   (optional)  'day' | 'week' | 'month'  (default: 'day')
	compareWith        : str   (optional)  'previous_period' | 'previous_year'
	viewMode           : str   (optional)  'total' | 'byService'  (default: 'total')
	movingAverageWindow: int   (optional)  0-30  (default: 0)
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request):
		serializer = KPIAggregationQuerySerializer(data=request.query_params)
		serializer.is_valid(raise_exception=True)
		data = serializer.validated_data

		payload = aggregate_kpi(
			start_date=data["start_date"],
			end_date=data["end_date"],
			group_by=data.get("groupBy", "day"),
			compare_with=data.get("compareWith"),
			view_mode=data.get("viewMode", "total"),
			moving_average_window=data.get("movingAverageWindow", 0),
		)

		return Response(payload, status=status.HTTP_200_OK)


class CohortRetentionView(APIView):
	"""
	GET /api/dashboard/membership/cohort

	Returns a cohort retention matrix.

	Query params
	------------
	endDate    : str  (required)  YYYY-MM-DD – reference end date
	monthsBack : int  (optional)  6-12  (default: 6)
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request):
		serializer = CohortQuerySerializer(data=request.query_params)
		serializer.is_valid(raise_exception=True)
		data = serializer.validated_data

		payload = build_cohort_matrix(
			end_date=data["end_date"],
			months_back=data.get("monthsBack", 6),
		)

		return Response(payload, status=status.HTTP_200_OK)


class AtRiskCustomerView(APIView):
	"""
	GET /api/dashboard/membership/at-risk

	Returns customers who are at risk of churning based on their
	booking frequency patterns.
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request):
		customers = find_at_risk_customers()

		payload = {
			"count": len(customers),
			"results": customers,
		}

		return Response(payload, status=status.HTTP_200_OK)


class PromoImpactView(APIView):
	"""
	GET /api/dashboard/membership/promo-impact

	Computes repeat-booking rate lift for each promo active in the period.

	Query params
	------------
	startDate   : str  (required)  YYYY-MM-DD
	endDate     : str  (required)  YYYY-MM-DD
	compareWith : str  (optional)  'previous_period' | 'previous_year'
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request):
		serializer = PromoImpactQuerySerializer(data=request.query_params)
		serializer.is_valid(raise_exception=True)
		data = serializer.validated_data

		results = compute_promo_impact(
			start_date=data["start_date"],
			end_date=data["end_date"],
			compare_with=data.get("compareWith"),
		)

		return Response(results, status=status.HTTP_200_OK)


class TherapistDetailReportView(APIView):
	"""
	GET /api/reports/therapist/<int:therapist_id>/detail

	Query params (required):
	- startDate: YYYY-MM-DD
	- endDate: YYYY-MM-DD
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request, therapist_id: int):
		query_serializer = TherapistPerformanceSummaryQuerySerializer(
			data=request.query_params
		)
		query_serializer.is_valid(raise_exception=True)

		start_date = query_serializer.validated_data["start_date"]
		end_date = query_serializer.validated_data["end_date"]

		detail = get_therapist_detail(therapist_id, start_date, end_date)
		if detail is None:
			return Response(
				{"message": "Data therapist tidak ditemukan di periode ini."},
				status=status.HTTP_404_NOT_FOUND,
			)

		return Response(detail, status=status.HTTP_200_OK)



class GlobalDateFilterView(APIView):
	"""
	GET /api/dashboard/date-filter

	Resolves a datePreset (or explicit startDate/endDate) and an optional
	comparisonMode into concrete date ranges.

	Query params
	------------
	datePreset          : str  today|yesterday|last_7_days|last_30_days|
	                           mtd|qtd|ytd|last_month|last_quarter|custom
	startDate           : str  YYYY-MM-DD (required when preset=custom or omitted)
	endDate             : str  YYYY-MM-DD (required when preset=custom or omitted)
	comparisonMode      : str  none (default)|previous_period|previous_year|custom
	comparisonStartDate : str  YYYY-MM-DD (required when comparisonMode=custom)
	comparisonEndDate   : str  YYYY-MM-DD (required when comparisonMode=custom)
	"""

	permission_classes = [IsAuthenticated, IsSupervisorOrOwner]

	def get(self, request):
		serializer = GlobalDateFilterSerializer(data=request.query_params)
		serializer.is_valid(raise_exception=True)
		data = serializer.validated_data

		start_date = data["start_date"]
		end_date = data["end_date"]
		preset = data.get("datePreset") or "custom"
		main_span_days = (end_date - start_date).days + 1

		comp_start = data.get("comp_start")
		comp_end = data.get("comp_end")
		comparison_mode = data.get("comparisonMode") or "none"

		comparison_payload = None
		if comp_start and comp_end:
			comparison_payload = {
				"startDate": comp_start.isoformat(),
				"endDate": comp_end.isoformat(),
				"spanDays": (comp_end - comp_start).days + 1,
			}

		payload = {
			"resolvedDateRange": {
				"preset": preset,
				"startDate": start_date.isoformat(),
				"endDate": end_date.isoformat(),
				"spanDays": main_span_days,
			},
			"comparisonMode": comparison_mode,
			"resolvedComparisonRange": comparison_payload,
		}

		return Response(payload, status=status.HTTP_200_OK)
