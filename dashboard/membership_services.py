"""
Business-logic layer for the Membership – Loyalty Visualization dashboard.

Three endpoints:
  1. Cohort retention matrix
  2. At-risk customer identification
  3. Promo impact analysis (repeat-booking rate)
"""

from datetime import date, timedelta

from django.db.models import Count, Max, Min
from django.utils import timezone

from booking.models import Booking
from event.models import Promo


# ═══════════════════════════════════════════════════════════════════════════
# 1. COHORT RETENTION  (AC 1-4)
# ═══════════════════════════════════════════════════════════════════════════

def _month_key(d: date) -> str:
    """Return 'YYYY-MM' string for grouping."""
    return d.strftime("%Y-%m")


def _month_diff(a: date, b: date) -> int:
    """Number of whole months from *a* to *b* (both inclusive of their month)."""
    return (b.year - a.year) * 12 + (b.month - a.month)


def _add_months(d: date, n: int) -> date:
    """Return *d* shifted forward by *n* months (clamped to last day)."""
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    # Clamp day to valid range
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, max_day))


def build_cohort_matrix(end_date: date, months_back: int = 6) -> dict:
    """
    Build a retention cohort matrix.

    Parameters
    ----------
    end_date : date
        The reference end date (usually "today").
    months_back : int
        Number of cohort months to look back (6–12, clamped).

    Returns
    -------
    dict with keys:
        cohortLabels  – list of 'YYYY-MM' cohort month labels (rows)
        periodLabels  – list of 'Month 0', 'Month 1', … (columns)
        matrix        – list of lists; each inner list = retention % per month
    """
    months_back = max(6, min(12, months_back))

    # ── Determine cohort window ────────────────────────────────────────
    cohort_start = _add_months(end_date.replace(day=1), -months_back + 1)
    cohort_end = end_date

    # ── All bookings with a valid phone number ─────────────────────────
    bookings = (
        Booking.objects.filter(
            no_hp__isnull=False,
        )
        .exclude(no_hp="")
        .values("no_hp", "tgl_treatment")
    )

    # ── Compute each customer's first-booking month ────────────────────
    first_booking = (
        bookings
        .values("no_hp")
        .annotate(first_date=Min("tgl_treatment"))
    )

    # Build lookup: customer -> first booking date
    customer_first: dict[str, date] = {}
    for row in first_booking:
        customer_first[row["no_hp"]] = row["first_date"]

    # ── Group customers into cohorts (by first-booking month) ──────────
    # cohort_customers[month_key] = set of phone numbers
    cohort_customers: dict[str, set[str]] = {}
    for phone, first_date in customer_first.items():
        mk = _month_key(first_date)
        # Only include cohorts within our window
        if cohort_start <= first_date.replace(day=1) <= cohort_end.replace(day=1):
            cohort_customers.setdefault(mk, set()).add(phone)

    # ── For each booking, record which (customer, month) pairs exist ───
    # activity[phone] = set of 'YYYY-MM' strings where they had a booking
    customer_activity: dict[str, set[str]] = {}
    for row in bookings:
        phone = row["no_hp"]
        if phone in customer_first:
            customer_activity.setdefault(phone, set()).add(
                _month_key(row["tgl_treatment"])
            )

    # ── Build the matrix ───────────────────────────────────────────────
    cohort_labels = sorted(cohort_customers.keys())
    max_periods = months_back  # columns: Month 0 .. Month (months_back-1)
    period_labels = [f"Month {i}" for i in range(max_periods)]

    matrix: list[list[float | None]] = []

    for cohort_month in cohort_labels:
        customers = cohort_customers[cohort_month]
        cohort_size = len(customers)
        row: list[float | None] = []

        # Parse cohort month back to a date (1st of month)
        cy, cm = map(int, cohort_month.split("-"))
        cohort_date = date(cy, cm, 1)

        for n in range(max_periods):
            target_month = _add_months(cohort_date, n)
            target_key = _month_key(target_month)

            # Don't compute retention for future months
            if target_month > end_date.replace(day=1):
                row.append(None)
                continue

            active_count = sum(
                1
                for phone in customers
                if target_key in customer_activity.get(phone, set())
            )

            pct = round((active_count / cohort_size) * 100, 1) if cohort_size else 0
            row.append(pct)

        matrix.append(row)

    return {
        "cohortLabels": cohort_labels,
        "periodLabels": period_labels,
        "matrix": matrix,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. AT-RISK CUSTOMERS  (AC 5-8)
# ═══════════════════════════════════════════════════════════════════════════

def _classify_risk(days_since: int, avg_gap: float) -> str:
    """
    Classify risk level based on how much the gap exceeds the average.

    - low:    1.5× – 2× avg
    - medium: 2×   – 3× avg
    - high:   > 3× avg
    """
    ratio = days_since / avg_gap if avg_gap > 0 else 999
    if ratio > 3:
        return "high"
    if ratio > 2:
        return "medium"
    return "low"


def find_at_risk_customers() -> list[dict]:
    """
    Identify at-risk customers: those with ≥3 completed bookings whose
    days-since-last-booking exceeds 1.5× their average inter-visit gap.

    Returns a list sorted by daysSinceLastBooking descending.
    """
    today = timezone.localdate()

    # ── Customers with ≥3 completed bookings ───────────────────────────
    customer_stats = (
        Booking.objects.filter(no_hp__isnull=False)
        .exclude(no_hp="")
        .values("no_hp")
        .annotate(
            total_bookings=Count("id"),
            first_booking=Min("tgl_treatment"),
            last_booking=Max("tgl_treatment"),
        )
        .filter(total_bookings__gte=3)
    )

    results: list[dict] = []

    for row in customer_stats:
        phone = row["no_hp"]
        total = row["total_bookings"]
        first_bk = row["first_booking"]
        last_bk = row["last_booking"]

        # Average days between visits
        span_days = (last_bk - first_bk).days
        if total <= 1 or span_days == 0:
            continue
        avg_gap = span_days / (total - 1)

        days_since = (today - last_bk).days

        # At-risk threshold: > 1.5× average gap
        if days_since <= avg_gap * 1.5:
            continue

        risk_level = _classify_risk(days_since, avg_gap)

        # Fetch latest name for this customer
        latest_booking = (
            Booking.objects.filter(no_hp=phone)
            .order_by("-tgl_treatment", "-jam_treatment")
            .values("nama")
            .first()
        )

        results.append(
            {
                "customerId": phone,
                "name": latest_booking["nama"] if latest_booking else "-",
                "phone": phone,
                "totalBookings": total,
                "lastBookingDate": last_bk.isoformat(),
                "daysSinceLastBooking": days_since,
                "riskLevel": risk_level,
            }
        )

    # Sort most at-risk first
    results.sort(key=lambda r: r["daysSinceLastBooking"], reverse=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════
# 3. PROMO IMPACT – REPEAT BOOKING RATE  (AC 9-15)
# ═══════════════════════════════════════════════════════════════════════════

def _repeat_booking_rate(start_date: date, end_date: date) -> float:
    """
    Compute repeat-booking rate for completed bookings in [start_date, end_date].

    Repeat rate = (customers with ≥2 bookings in period) / (total unique customers)
    Returns a float 0-100 (percentage).
    """
    customer_counts = (
        Booking.objects.filter(
            status=Booking.BookingStatus.COMPLETED,
            tgl_treatment__gte=start_date,
            tgl_treatment__lte=end_date,
            no_hp__isnull=False,
        )
        .exclude(no_hp="")
        .values("no_hp")
        .annotate(booking_count=Count("id"))
    )

    total_customers = customer_counts.count()
    if total_customers == 0:
        return 0.0

    repeat_customers = customer_counts.filter(booking_count__gte=2).count()
    return round((repeat_customers / total_customers) * 100, 2)


def compute_promo_impact(
    *,
    start_date: date,
    end_date: date,
    compare_with: str | None = None,
) -> list[dict]:
    """
    For each active/expired promo overlapping [start_date, end_date]:
      - Compute repeat-booking rate during the promo
      - Compute baseline repeat-booking rate (30 days before promo start)
      - Compute lift = (during − baseline) / baseline × 100
      - If compareWith is set, compute previousPeriodRepeatRate and delta

    Returns list of per-promo dicts.
    """
    promos = Promo.active_objects.filter(
        content_type=Promo.ContentType.PROMO,
        posting_state=Promo.PostingState.PUBLISHED,
        start_date__isnull=False,
        end_date__isnull=False,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    results: list[dict] = []

    for promo in promos:
        # ── Promo period ───────────────────────────────────────────────
        promo_start = promo.start_date
        promo_end = promo.end_date

        # ── Baseline: 30 days before promo start ──────────────────────
        baseline_end = promo_start - timedelta(days=1)
        baseline_start = promo_start - timedelta(days=30)

        during_rate = _repeat_booking_rate(promo_start, promo_end)
        baseline_rate = _repeat_booking_rate(baseline_start, baseline_end)

        # Lift (AC 12)
        if baseline_rate > 0:
            lift = round((during_rate - baseline_rate) / baseline_rate * 100, 2)
        else:
            lift = None  # Cannot compute lift with zero baseline

        entry: dict = {
            "promoId": promo.id,
            "title": promo.title,
            "periode": {
                "startDate": promo_start.isoformat(),
                "endDate": promo_end.isoformat(),
            },
            "baselineRepeatRate": baseline_rate,
            "duringPromoRepeatRate": during_rate,
            "lift": lift,
        }

        # ── Comparison period (AC 13-15) ──────────────────────────────
        if compare_with:
            prev_start, prev_end = _promo_comparison_range(
                promo_start, promo_end, compare_with
            )
            prev_rate = _repeat_booking_rate(prev_start, prev_end)
            delta = round(during_rate - prev_rate, 2)  # percentage points (AC 15)

            entry["previousPeriodRepeatRate"] = prev_rate
            entry["deltaRepeatRate"] = delta
        else:
            entry["previousPeriodRepeatRate"] = None
            entry["deltaRepeatRate"] = None

        results.append(entry)

    return results


def _promo_comparison_range(
    promo_start: date, promo_end: date, compare_with: str
) -> tuple[date, date]:
    """Calculate the comparison window for a promo's own date range."""
    if compare_with == "previous_period":
        duration = (promo_end - promo_start).days + 1
        comp_end = promo_start - timedelta(days=1)
        comp_start = comp_end - timedelta(days=duration - 1)
        return comp_start, comp_end

    # previous_year
    try:
        comp_start = promo_start.replace(year=promo_start.year - 1)
    except ValueError:
        comp_start = promo_start.replace(year=promo_start.year - 1, day=28)
    try:
        comp_end = promo_end.replace(year=promo_end.year - 1)
    except ValueError:
        comp_end = promo_end.replace(year=promo_end.year - 1, day=28)
    return comp_start, comp_end
