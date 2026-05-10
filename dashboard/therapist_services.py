"""
Therapist retention & deep-view services (AC 17-21).
"""

from datetime import date, timedelta

from django.db.models import Avg, Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce, TruncDay

from booking.models import Booking
from review.models import Review


# ═══════════════════════════════════════════════════════════════════════════
# AC 17-19 – clientRetentionRate per therapist
# ═══════════════════════════════════════════════════════════════════════════

def compute_therapist_retention(
    therapist_id: int,
    start_date: date,
    end_date: date,
) -> float | None:
    """
    clientRetentionRate = (customers who completed ≥2 bookings with
                           the SAME therapist in period) / unique customers × 100.

    Only COMPLETED bookings are counted (AC 19).
    Returns None when there are no customers for this therapist.
    """
    qs = (
        Booking.objects.filter(
            therapist_id=therapist_id,
            status=Booking.BookingStatus.COMPLETED,
            tgl_treatment__gte=start_date,
            tgl_treatment__lte=end_date,
            no_hp__isnull=False,
        )
        .exclude(no_hp="")
        .values("no_hp")
        .annotate(visit_count=Count("id"))
    )

    total_unique = qs.count()
    if total_unique == 0:
        return None

    re_bookers = qs.filter(visit_count__gte=2).count()
    return round((re_bookers / total_unique) * 100, 1)


def compute_all_therapist_retentions(
    therapist_ids: list[int],
    start_date: date,
    end_date: date,
) -> dict[int, float | None]:
    """Batch computation for multiple therapists."""
    return {
        tid: compute_therapist_retention(tid, start_date, end_date)
        for tid in therapist_ids
    }


# ═══════════════════════════════════════════════════════════════════════════
# AC 20-21 – Single-therapist deep view
# ═══════════════════════════════════════════════════════════════════════════

def _day_series(
    therapist_id: int,
    metric: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Return a daily time-series over [start_date, end_date].

    metric: 'bookings' | 'revenue' | 'rating'
    """
    base_qs = Booking.objects.filter(
        therapist_id=therapist_id,
        status=Booking.BookingStatus.COMPLETED,
        tgl_treatment__gte=start_date,
        tgl_treatment__lte=end_date,
    )

    if metric == "rating":
        qs = (
            base_qs.annotate(day=TruncDay("tgl_treatment"))
            .values("day")
            .annotate(value=Avg("review__rating"))
            .order_by("day")
        )
        raw = {
            (r["day"].date() if hasattr(r["day"], "date") else r["day"]):
            (round(float(r["value"]), 2) if r["value"] is not None else None)
            for r in qs
        }
    elif metric == "revenue":
        qs = (
            base_qs.annotate(day=TruncDay("tgl_treatment"))
            .values("day")
            .annotate(
                value=Coalesce(
                    Sum("total_pembayaran"),
                    Value(0, output_field=DecimalField()),
                )
            )
            .order_by("day")
        )
        raw = {
            (r["day"].date() if hasattr(r["day"], "date") else r["day"]):
            float(r["value"])
            for r in qs
        }
    else:  # bookings
        qs = (
            base_qs.annotate(day=TruncDay("tgl_treatment"))
            .values("day")
            .annotate(value=Count("id"))
            .order_by("day")
        )
        raw = {
            (r["day"].date() if hasattr(r["day"], "date") else r["day"]):
            r["value"]
            for r in qs
        }

    # Fill every day in the window
    result = []
    cur = start_date
    while cur <= end_date:
        result.append({
            "date": cur.isoformat(),
            "value": raw.get(cur, 0 if metric != "rating" else None),
        })
        cur += timedelta(days=1)
    return result


def get_therapist_detail(
    therapist_id: int,
    start_date: date,
    end_date: date,
) -> dict | None:
    """
    Return deep-view payload for a single therapist (AC 21).

    Returns None if the therapist has no completed bookings in the period.
    """
    # ── Summary metrics ────────────────────────────────────────────────
    completed_qs = Booking.objects.filter(
        therapist_id=therapist_id,
        status=Booking.BookingStatus.COMPLETED,
        tgl_treatment__gte=start_date,
        tgl_treatment__lte=end_date,
    )

    agg = completed_qs.aggregate(
        total_bookings=Count("id"),
        total_revenue=Coalesce(
            Sum("total_pembayaran"),
            Value(0, output_field=DecimalField()),
        ),
    )

    total_bookings = agg["total_bookings"] or 0
    if total_bookings == 0:
        return None

    total_revenue = float(agg["total_revenue"] or 0)

    cancelled_count = Booking.objects.filter(
        therapist_id=therapist_id,
        status=Booking.BookingStatus.CANCELLED,
        tgl_treatment__gte=start_date,
        tgl_treatment__lte=end_date,
    ).count()

    avg_rating_row = Review.objects.filter(
        therapist_id=therapist_id,
        booking__tgl_treatment__gte=start_date,
        booking__tgl_treatment__lte=end_date,
    ).aggregate(avg=Avg("rating"))
    avg_rating = (
        round(float(avg_rating_row["avg"]), 2)
        if avg_rating_row["avg"] is not None
        else None
    )

    client_retention = compute_therapist_retention(
        therapist_id, start_date, end_date
    )

    # ── 30-day time-series window ──────────────────────────────────────
    series_end = end_date
    series_start = series_end - timedelta(days=29)

    # ── Recent reviews (latest 10) ─────────────────────────────────────
    recent_reviews_qs = (
        Review.objects.filter(therapist_id=therapist_id)
        .select_related("booking")
        .order_by("-created_at")[:10]
        .values(
            "id",
            "rating",
            "comment",
            "customer_name",
            "customer_phone",
            "created_at",
            "booking__booking_id",
            "booking__tgl_treatment",
        )
    )

    reviews_payload = [
        {
            "reviewId": r["id"],
            "bookingId": r["booking__booking_id"],
            "treatmentDate": (
                r["booking__tgl_treatment"].isoformat()
                if r["booking__tgl_treatment"]
                else None
            ),
            "rating": r["rating"],
            "comment": r["comment"],
            "customerName": r["customer_name"],
            "customerPhone": r["customer_phone"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in recent_reviews_qs
    ]

    return {
        "therapistId": therapist_id,
        "period": {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
        "summary": {
            "totalBookings": total_bookings,
            "completedBookings": total_bookings,
            "cancelledBookings": cancelled_count,
            "totalRevenue": total_revenue,
            "averageRating": avg_rating,
            "clientRetentionRate": client_retention,
        },
        "timeSeries": {
            "window": {
                "startDate": series_start.isoformat(),
                "endDate": series_end.isoformat(),
            },
            "bookings": _day_series(
                therapist_id, "bookings", series_start, series_end
            ),
            "revenue": _day_series(
                therapist_id, "revenue", series_start, series_end
            ),
            "rating": _day_series(
                therapist_id, "rating", series_start, series_end
            ),
        },
        "recentReviews": reviews_payload,
    }
