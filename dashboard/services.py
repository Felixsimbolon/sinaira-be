"""
Business-logic layer for the Executive KPI Dashboard.

All heavy aggregation lives here so the view stays thin.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek

from booking.models import Booking
from event.helpers import compute_promo_status
from event.models import Promo
from layanan.models import Layanan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRUNC_MAP = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
}


def _trunc_fn(group_by: str):
    return _TRUNC_MAP.get(group_by, TruncDay)


def _generate_period_list(start_date: date, end_date: date, group_by: str) -> list[date]:
    """Return every period-start date that falls within [start_date, end_date]."""
    periods: list[date] = []

    if group_by == "day":
        cur = start_date
        while cur <= end_date:
            periods.append(cur)
            cur += timedelta(days=1)

    elif group_by == "week":
        # Align to ISO Monday
        cur = start_date - timedelta(days=start_date.weekday())
        while cur <= end_date:
            periods.append(cur)
            cur += timedelta(weeks=1)

    elif group_by == "month":
        cur = start_date.replace(day=1)
        while cur <= end_date:
            periods.append(cur)
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1)
            else:
                cur = cur.replace(month=cur.month + 1)

    return periods


def _comparison_range(
    start_date: date, end_date: date, compare_with: str
) -> tuple[date, date]:
    """Calculate the comparison window."""
    if compare_with == "previous_period":
        duration = (end_date - start_date).days + 1
        comp_end = start_date - timedelta(days=1)
        comp_start = comp_end - timedelta(days=duration - 1)
        return comp_start, comp_end

    # previous_year
    try:
        comp_start = start_date.replace(year=start_date.year - 1)
    except ValueError:  # Feb-29 edge case
        comp_start = start_date.replace(year=start_date.year - 1, day=28)
    try:
        comp_end = end_date.replace(year=end_date.year - 1)
    except ValueError:
        comp_end = end_date.replace(year=end_date.year - 1, day=28)
    return comp_start, comp_end


def _normalize_period(val) -> date:
    """TruncDay/Week/Month may return datetime; normalise to date."""
    return val.date() if hasattr(val, "date") else val


# ---------------------------------------------------------------------------
# Total-mode queries
# ---------------------------------------------------------------------------

def _completed_bookings(start_date: date, end_date: date):
    return Booking.objects.filter(
        status=Booking.BookingStatus.COMPLETED,
        tgl_treatment__gte=start_date,
        tgl_treatment__lte=end_date,
    )


def _revenue_series_total(
    start_date: date, end_date: date, group_by: str, period_list: list[date]
) -> list[dict]:
    trunc = _trunc_fn(group_by)
    qs = (
        _completed_bookings(start_date, end_date)
        .annotate(periode=trunc("tgl_treatment"))
        .values("periode")
        .annotate(
            revenue=Coalesce(
                Sum("total_pembayaran"),
                Value(0, output_field=DecimalField()),
            ),
        )
        .order_by("periode")
    )
    rev_map = {
        _normalize_period(r["periode"]): float(r["revenue"]) for r in qs
    }
    return [
        {"periode": p.isoformat(), "revenue": rev_map.get(p, 0)}
        for p in period_list
    ]


def _booking_count_series_total(
    start_date: date, end_date: date, group_by: str, period_list: list[date]
) -> list[dict]:
    trunc = _trunc_fn(group_by)
    qs = (
        _completed_bookings(start_date, end_date)
        .annotate(periode=trunc("tgl_treatment"))
        .values("periode")
        .annotate(count=Count("id"))
        .order_by("periode")
    )
    cnt_map = {
        _normalize_period(r["periode"]): r["count"] for r in qs
    }
    return [
        {"periode": p.isoformat(), "count": cnt_map.get(p, 0)}
        for p in period_list
    ]


# ---------------------------------------------------------------------------
# By-service-mode queries
# ---------------------------------------------------------------------------

def _series_by_service(
    start_date: date, end_date: date, group_by: str, period_list: list[date],
    restrict_service_ids: list[int] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Return (revenueSeries, bookingCountSeries) broken down per service.

    If *restrict_service_ids* is given the result will contain exactly those
    services (used for comparison alignment).
    """
    trunc = _trunc_fn(group_by)
    BookingLayanan = Booking.layanans.through  # noqa: N806

    base_filter = dict(
        booking__status=Booking.BookingStatus.COMPLETED,
        booking__tgl_treatment__gte=start_date,
        booking__tgl_treatment__lte=end_date,
    )

    # ── Discover relevant service IDs ──────────────────────────────────
    if restrict_service_ids is not None:
        service_ids = restrict_service_ids
    else:
        service_ids = list(
            BookingLayanan.objects.filter(**base_filter)
            .values_list("layanan_id", flat=True)
            .distinct()
        )

    services = Layanan.objects.filter(id__in=service_ids).order_by("nama")

    # ── Aggregate per (layanan, period) ────────────────────────────────
    data_qs = (
        BookingLayanan.objects.filter(**base_filter, layanan_id__in=service_ids)
        .annotate(periode=trunc("booking__tgl_treatment"))
        .values("layanan_id", "layanan__nama", "layanan__layanan_id", "periode")
        .annotate(
            revenue=Coalesce(
                Sum("layanan__harga"), Value(0, output_field=DecimalField())
            ),
            count=Count("booking_id", distinct=True),
        )
        .order_by("layanan__nama", "periode")
    )

    svc_data: dict[int, dict[date, dict]] = {}
    for row in data_qs:
        lid = row["layanan_id"]
        p = _normalize_period(row["periode"])
        svc_data.setdefault(lid, {})[p] = {
            "revenue": float(row["revenue"]),
            "count": row["count"],
        }

    revenue_series: list[dict] = []
    booking_count_series: list[dict] = []

    for svc in services:
        lookup = svc_data.get(svc.id, {})

        rev_points = []
        cnt_points = []
        for p in period_list:
            point = lookup.get(p, {"revenue": 0, "count": 0})
            rev_points.append({"periode": p.isoformat(), "revenue": point["revenue"]})
            cnt_points.append({"periode": p.isoformat(), "count": point["count"]})

        revenue_series.append(
            {
                "serviceName": svc.nama,
                "serviceId": svc.layanan_id,
                "dataPoints": rev_points,
            }
        )
        booking_count_series.append(
            {
                "serviceName": svc.nama,
                "serviceId": svc.layanan_id,
                "dataPoints": cnt_points,
            }
        )

    return revenue_series, booking_count_series


# ---------------------------------------------------------------------------
# Promo annotations (req 9-11)
# ---------------------------------------------------------------------------

def _promo_annotations(start_date: date, end_date: date) -> list[dict]:
    """
    Return promos whose date window overlaps [start_date, end_date] and whose
    computed status is 'active' or 'expired' (never 'scheduled').
    """
    promos = Promo.active_objects.filter(
        start_date__isnull=False,
        end_date__isnull=False,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    annotations: list[dict] = []
    for promo in promos:
        status = compute_promo_status(
            start_date=promo.start_date,
            end_date=promo.end_date,
        )
        if status in ("active", "expired"):
            annotations.append(
                {
                    "promoId": promo.id,
                    "title": promo.title,
                    "startDate": promo.start_date.isoformat(),
                    "endDate": promo.end_date.isoformat(),
                }
            )
    return annotations


# ---------------------------------------------------------------------------
# Moving average (req 15-17)
# ---------------------------------------------------------------------------

def _simple_moving_average(series: list[dict], window: int) -> list[dict] | None:
    """
    Compute SMA over a flat series (total mode).

    Returns *None* when window > len(series).
    """
    if not series or window <= 0:
        return None

    value_key = "revenue" if "revenue" in series[0] else "count"
    values = [point[value_key] for point in series]

    if window > len(values):
        return None

    ma: list[dict] = []
    for i, point in enumerate(series):
        if i < window - 1:
            ma.append({"periode": point["periode"], "value": None})
        else:
            avg = sum(values[i - window + 1 : i + 1]) / window
            ma.append({"periode": point["periode"], "value": round(avg, 2)})
    return ma


def _moving_average_by_service(
    revenue_series: list[dict], window: int
) -> list[dict] | None:
    """Compute SMA per service entry (byService mode)."""
    if not revenue_series:
        return None

    result: list[dict] = []
    for entry in revenue_series:
        data_points = entry["dataPoints"]
        if window > len(data_points):
            return None  # req 17
        ma = _simple_moving_average(data_points, window)
        result.append(
            {
                "serviceName": entry["serviceName"],
                "serviceId": entry["serviceId"],
                "dataPoints": ma,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Alignment helpers for comparison series (req 3-4)
# ---------------------------------------------------------------------------

def _align_flat_series(
    comp_series: list[dict], main_len: int, zero_key: str = "revenue"
) -> list[dict]:
    """
    Ensure *comp_series* has exactly *main_len* data points.
    Pads with zeroes or trims from the end as needed.
    """
    if len(comp_series) >= main_len:
        return comp_series[:main_len]

    # Pad with zero-value entries
    last_period = comp_series[-1]["periode"] if comp_series else "0000-00-00"
    while len(comp_series) < main_len:
        comp_series.append({"periode": last_period, zero_key: 0})
    return comp_series


def _align_service_series(
    comp_series: list[dict], main_len: int, zero_key: str = "revenue"
) -> list[dict]:
    """Align each service entry's dataPoints to *main_len*."""
    for entry in comp_series:
        entry["dataPoints"] = _align_flat_series(
            entry["dataPoints"], main_len, zero_key
        )
    return comp_series


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def aggregate_kpi(
    *,
    start_date: date,
    end_date: date,
    group_by: str = "day",
    compare_with: str | None = None,
    view_mode: str = "total",
    moving_average_window: int = 0,
) -> dict:
    """
    Orchestrate the full KPI aggregation and return the response payload.
    """
    period_list = _generate_period_list(start_date, end_date, group_by)

    result: dict = {
        "period": {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "groupBy": group_by,
        },
    }

    # ── Main series ────────────────────────────────────────────────────
    if view_mode == "byService":
        revenue_series, booking_count_series = _series_by_service(
            start_date, end_date, group_by, period_list
        )
        # Collect service IDs used in main period for comparison alignment
        main_service_ids = list(
            Layanan.objects.filter(
                layanan_id__in=[s["serviceId"] for s in revenue_series]
            ).values_list("id", flat=True)
        )
    else:
        revenue_series = _revenue_series_total(
            start_date, end_date, group_by, period_list
        )
        booking_count_series = _booking_count_series_total(
            start_date, end_date, group_by, period_list
        )

    result["revenueSeries"] = revenue_series
    result["bookingCountSeries"] = booking_count_series

    # ── Comparison series (req 1-4) ────────────────────────────────────
    if compare_with:
        comp_start, comp_end = _comparison_range(start_date, end_date, compare_with)
        comp_period_list = _generate_period_list(comp_start, comp_end, group_by)

        if view_mode == "byService":
            comp_rev, comp_cnt = _series_by_service(
                comp_start,
                comp_end,
                group_by,
                comp_period_list,
                restrict_service_ids=main_service_ids,
            )
            main_dp_len = (
                len(revenue_series[0]["dataPoints"]) if revenue_series else 0
            )
            comp_rev = _align_service_series(comp_rev, main_dp_len, "revenue")
            comp_cnt = _align_service_series(comp_cnt, main_dp_len, "count")
        else:
            comp_rev = _revenue_series_total(
                comp_start, comp_end, group_by, comp_period_list
            )
            comp_cnt = _booking_count_series_total(
                comp_start, comp_end, group_by, comp_period_list
            )
            main_len = len(revenue_series)
            comp_rev = _align_flat_series(comp_rev, main_len, "revenue")
            comp_cnt = _align_flat_series(comp_cnt, main_len, "count")

        result["comparisonSeries"] = {
            "period": {
                "startDate": comp_start.isoformat(),
                "endDate": comp_end.isoformat(),
            },
            "revenueSeries": comp_rev,
            "bookingCountSeries": comp_cnt,
        }

    # ── Promo annotations (req 9-11) ──────────────────────────────────
    result["promoAnnotations"] = _promo_annotations(start_date, end_date)

    # ── Moving average (req 15-17) ────────────────────────────────────
    if moving_average_window > 0:
        if view_mode == "byService":
            result["movingAverageSeries"] = _moving_average_by_service(
                revenue_series, moving_average_window
            )
        else:
            result["movingAverageSeries"] = _simple_moving_average(
                revenue_series, moving_average_window
            )

    return result
