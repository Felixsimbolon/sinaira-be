"""
Date utility helpers for the dashboard Global Date Filter.

Responsibilities
----------------
- Convert datePreset strings → (start_date, end_date) in WIB (Asia/Jakarta).
- Validate comparisonMode and its custom date range.
- Centralised parse helper so serializers stay clean.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from rest_framework import serializers

# ── Timezone ──────────────────────────────────────────────────────────────────
WIB = ZoneInfo("Asia/Jakarta")

# ── Valid presets ─────────────────────────────────────────────────────────────
VALID_PRESETS = frozenset(
    [
        "today",
        "yesterday",
        "last_7_days",
        "last_30_days",
        "mtd",       # month-to-date
        "qtd",       # quarter-to-date
        "ytd",       # year-to-date
        "last_month",
        "last_quarter",
        "custom",
    ]
)

VALID_COMPARISON_MODES = frozenset(
    ["none", "previous_period", "previous_year", "custom"]
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today_wib() -> date:
    """Return today's date in WIB timezone."""
    from django.utils import timezone as dj_tz
    return dj_tz.now().astimezone(WIB).date()


def _quarter_start(d: date) -> date:
    """Return the first day of the quarter containing *d*."""
    quarter_start_month = ((d.month - 1) // 3) * 3 + 1
    return d.replace(month=quarter_start_month, day=1)


def _last_quarter_range(d: date) -> tuple[date, date]:
    """Return (start, end) of the calendar quarter before *d*'s quarter."""
    # First day of current quarter
    cur_q_start = _quarter_start(d)
    # Last day of previous quarter
    prev_q_end = cur_q_start - timedelta(days=1)
    # First day of previous quarter
    prev_q_start = _quarter_start(prev_q_end)
    return prev_q_start, prev_q_end


def _last_month_range(d: date) -> tuple[date, date]:
    """Return (start, end) of the calendar month before *d*'s month."""
    first_of_current = d.replace(day=1)
    last_of_prev = first_of_current - timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)
    return first_of_prev, last_of_prev


# ── Public: preset resolver ───────────────────────────────────────────────────

def resolve_preset(preset: str) -> tuple[date, date]:
    """
    Convert a datePreset string to (start_date, end_date) using WIB server time.

    Raises
    ------
    serializers.ValidationError  if *preset* is not in VALID_PRESETS or is
                                  'custom' (caller must supply explicit dates).
    """
    if preset not in VALID_PRESETS:
        raise serializers.ValidationError(
            {
                "datePreset": (
                    f"Nilai datePreset '{preset}' tidak valid. "
                    f"Nilai yang diizinkan: {sorted(VALID_PRESETS)}."
                )
            }
        )

    if preset == "custom":
        # Caller is responsible for supplying startDate + endDate explicitly.
        raise ValueError("preset='custom' must be resolved by the caller")

    today = _today_wib()

    if preset == "today":
        return today, today

    if preset == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday

    if preset == "last_7_days":
        return today - timedelta(days=6), today

    if preset == "last_30_days":
        return today - timedelta(days=29), today

    if preset == "mtd":
        return today.replace(day=1), today

    if preset == "qtd":
        return _quarter_start(today), today

    if preset == "ytd":
        return today.replace(month=1, day=1), today

    if preset == "last_month":
        return _last_month_range(today)

    if preset == "last_quarter":
        return _last_quarter_range(today)

    # Should never reach here, but keep as safety net
    raise serializers.ValidationError(
        {"datePreset": f"Preset '{preset}' belum diimplementasikan."}
    )


# ── Public: comparison range resolver ────────────────────────────────────────

def resolve_comparison_range(
    *,
    comparison_mode: str,
    main_start: date,
    main_end: date,
    comparison_start_raw: str | None = None,
    comparison_end_raw: str | None = None,
) -> tuple[date, date] | None:
    """
    Derive the comparison (start, end) from *comparison_mode*.

    Returns None when comparison_mode is 'none'.

    Validates:
    - 'custom' requires both comparisonStartDate and comparisonEndDate (AC 7).
    - Comparison span ≤ main span (AC 8-9).

    Raises serializers.ValidationError on any violation.
    """
    if comparison_mode == "none":
        return None

    if comparison_mode == "previous_period":
        duration = (main_end - main_start).days + 1
        comp_end = main_start - timedelta(days=1)
        comp_start = comp_end - timedelta(days=duration - 1)
        return comp_start, comp_end

    if comparison_mode == "previous_year":
        try:
            comp_start = main_start.replace(year=main_start.year - 1)
        except ValueError:
            comp_start = main_start.replace(year=main_start.year - 1, day=28)
        try:
            comp_end = main_end.replace(year=main_end.year - 1)
        except ValueError:
            comp_end = main_end.replace(year=main_end.year - 1, day=28)
        return comp_start, comp_end

    if comparison_mode == "custom":
        # AC 7 – both fields are mandatory
        if not comparison_start_raw or not comparison_end_raw:
            raise serializers.ValidationError(
                {
                    "comparisonStartDate": (
                        "comparisonStartDate dan comparisonEndDate wajib diisi "
                        "jika comparisonMode = 'custom'."
                    )
                }
            )

        try:
            comp_start = date.fromisoformat(comparison_start_raw)
        except ValueError:
            raise serializers.ValidationError(
                {
                    "comparisonStartDate": (
                        "Format comparisonStartDate tidak valid. Gunakan YYYY-MM-DD."
                    )
                }
            )

        try:
            comp_end = date.fromisoformat(comparison_end_raw)
        except ValueError:
            raise serializers.ValidationError(
                {
                    "comparisonEndDate": (
                        "Format comparisonEndDate tidak valid. Gunakan YYYY-MM-DD."
                    )
                }
            )

        if comp_start > comp_end:
            raise serializers.ValidationError(
                {
                    "comparisonDateRange": (
                        "comparisonStartDate tidak boleh lebih besar dari "
                        "comparisonEndDate."
                    )
                }
            )

        # AC 8-9 – comparison span must not exceed main span
        main_span = (main_end - main_start).days + 1
        comp_span = (comp_end - comp_start).days + 1
        if comp_span > main_span:
            raise serializers.ValidationError(
                {
                    "comparisonDateRange": (
                        f"Rentang periode pembanding ({comp_span} hari) tidak boleh "
                        f"lebih besar dari rentang utama ({main_span} hari). "
                        "Pastikan rentang comparison ≤ rentang utama untuk "
                        "perbandingan yang adil (fair comparison)."
                    )
                }
            )

        return comp_start, comp_end

    # Invalid mode – should have been caught by field-level validation
    raise serializers.ValidationError(
        {
            "comparisonMode": (
                f"Nilai comparisonMode '{comparison_mode}' tidak valid. "
                f"Nilai yang diizinkan: {sorted(VALID_COMPARISON_MODES)}."
            )
        }
    )


# ── Public: parse a raw date string ──────────────────────────────────────────

def parse_date(raw: str, field_name: str) -> date:
    """
    Parse *raw* as YYYY-MM-DD, raising a serializer ValidationError on failure.
    """
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise serializers.ValidationError(
            {field_name: f"Format {field_name} tidak valid. Gunakan YYYY-MM-DD."}
        )
