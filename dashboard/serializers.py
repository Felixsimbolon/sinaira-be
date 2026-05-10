from datetime import datetime

from rest_framework import serializers

from .date_utils import (
    VALID_COMPARISON_MODES,
    VALID_PRESETS,
    parse_date,
    resolve_comparison_range,
    resolve_preset,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared mixin: resolves datePreset OR startDate/endDate into start_date/end_date
# ─────────────────────────────────────────────────────────────────────────────

class DateRangeMixin:
    """
    Mixin that adds datePreset support on top of explicit startDate/endDate.

    Rules (AC 1-5)
    --------------
    - If datePreset is given and != 'custom', startDate/endDate are derived
      from the preset using Asia/Jakarta server time.
    - If datePreset == 'custom', startDate and endDate are both required.
    - If datePreset is omitted, startDate and endDate are both required.
    - An unknown preset returns 400.
    """

    def _resolve_date_range(self, attrs: dict) -> dict:
        preset = attrs.get("datePreset")
        start_raw = attrs.get("startDate")
        end_raw = attrs.get("endDate")

        if preset and preset != "custom":
            # AC 3 – convert preset → dates using WIB
            start_date, end_date = resolve_preset(preset)

        elif preset == "custom":
            # AC 5 – both fields are mandatory for custom
            errors = {}
            if not start_raw:
                errors["startDate"] = (
                    "startDate wajib diisi jika datePreset = 'custom'."
                )
            if not end_raw:
                errors["endDate"] = (
                    "endDate wajib diisi jika datePreset = 'custom'."
                )
            if errors:
                raise serializers.ValidationError(errors)
            start_date = parse_date(start_raw, "startDate")
            end_date = parse_date(end_raw, "endDate")

        else:
            # No preset – explicit dates required
            errors = {}
            if not start_raw:
                errors["startDate"] = (
                    "startDate wajib diisi (atau gunakan datePreset)."
                )
            if not end_raw:
                errors["endDate"] = (
                    "endDate wajib diisi (atau gunakan datePreset)."
                )
            if errors:
                raise serializers.ValidationError(errors)
            start_date = parse_date(start_raw, "startDate")
            end_date = parse_date(end_raw, "endDate")

        if start_date > end_date:
            raise serializers.ValidationError(
                {"dateRange": "startDate tidak boleh lebih besar dari endDate."}
            )

        attrs["start_date"] = start_date
        attrs["end_date"] = end_date
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# Shared mixin: resolves comparisonMode → comp_start / comp_end
# ─────────────────────────────────────────────────────────────────────────────

class ComparisonModeMixin:
    """
    Mixin that resolves comparisonMode (AC 6-9) once start_date/end_date exist.
    """

    def _resolve_comparison(self, attrs: dict) -> dict:
        mode = attrs.get("comparisonMode", "none") or "none"
        comp_range = resolve_comparison_range(
            comparison_mode=mode,
            main_start=attrs["start_date"],
            main_end=attrs["end_date"],
            comparison_start_raw=attrs.get("comparisonStartDate"),
            comparison_end_raw=attrs.get("comparisonEndDate"),
        )
        if comp_range:
            attrs["comp_start"], attrs["comp_end"] = comp_range
        else:
            attrs["comp_start"] = None
            attrs["comp_end"] = None
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# Existing serializers (unchanged logic, kept for backward compat)
# ─────────────────────────────────────────────────────────────────────────────

class TherapistPerformanceSummaryQuerySerializer(serializers.Serializer):
    startDate = serializers.CharField(required=True)
    endDate = serializers.CharField(required=True)

    def validate(self, attrs):
        start_raw = attrs.get("startDate")
        end_raw = attrs.get("endDate")

        try:
            start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"startDate": "Format startDate tidak valid. Gunakan YYYY-MM-DD."}
            )

        try:
            end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"endDate": "Format endDate tidak valid. Gunakan YYYY-MM-DD."}
            )

        if start_date > end_date:
            raise serializers.ValidationError(
                {"dateRange": "startDate tidak boleh lebih besar dari endDate."}
            )

        attrs["start_date"] = start_date
        attrs["end_date"] = end_date
        return attrs


class KPIAggregationQuerySerializer(DateRangeMixin, serializers.Serializer):
    """
    Validates query-params for GET /api/dashboard/kpi.

    Supports both explicit startDate/endDate AND datePreset shorthand (AC 1-5).
    Also supports comparisonMode (AC 6-9) replacing the old compareWith field.
    compareWith is kept as a legacy alias (maps to comparisonMode).
    """

    # ── Date range (preset OR explicit) ──────────────────────────────────────
    datePreset = serializers.ChoiceField(
        choices=list(VALID_PRESETS),
        required=False,
        allow_null=True,
        default=None,
    )
    startDate = serializers.CharField(required=False, allow_blank=True, default="")
    endDate = serializers.CharField(required=False, allow_blank=True, default="")

    # ── Comparison ────────────────────────────────────────────────────────────
    comparisonMode = serializers.ChoiceField(
        choices=list(VALID_COMPARISON_MODES),
        required=False,
        allow_null=True,
        default="none",
    )
    comparisonStartDate = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    comparisonEndDate = serializers.CharField(
        required=False, allow_blank=True, default=""
    )

    # ── Legacy alias kept for backward compat ─────────────────────────────────
    compareWith = serializers.ChoiceField(
        choices=["previous_period", "previous_year"],
        required=False,
        allow_null=True,
        default=None,
    )

    # ── Other KPI params ─────────────────────────────────────────────────────
    groupBy = serializers.ChoiceField(
        choices=["day", "week", "month"],
        default="day",
        required=False,
    )
    viewMode = serializers.ChoiceField(
        choices=["total", "byService"],
        default="total",
        required=False,
    )
    movingAverageWindow = serializers.IntegerField(
        min_value=0,
        max_value=30,
        default=0,
        required=False,
    )

    def validate(self, attrs):
        # 1. Resolve main date range
        attrs = self._resolve_date_range(attrs)

        # 2. Resolve comparison — comparisonMode takes priority over legacy compareWith
        mode = attrs.get("comparisonMode") or "none"
        if mode == "none" and attrs.get("compareWith"):
            # Map legacy compareWith → comparisonMode so services still work
            mode = attrs["compareWith"]
            attrs["comparisonMode"] = mode

        if mode and mode != "none":
            from .date_utils import resolve_comparison_range as _rcr
            comp = _rcr(
                comparison_mode=mode,
                main_start=attrs["start_date"],
                main_end=attrs["end_date"],
                comparison_start_raw=attrs.get("comparisonStartDate") or None,
                comparison_end_raw=attrs.get("comparisonEndDate") or None,
            )
            if comp:
                attrs["comp_start"], attrs["comp_end"] = comp
        else:
            attrs["comp_start"] = None
            attrs["comp_end"] = None

        return attrs


class CohortQuerySerializer(serializers.Serializer):
    """Validates query-params for GET /api/dashboard/membership/cohort."""

    endDate = serializers.CharField(required=True)
    monthsBack = serializers.IntegerField(
        min_value=6,
        max_value=12,
        default=6,
        required=False,
    )

    def validate(self, attrs):
        end_raw = attrs.get("endDate")
        try:
            end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"endDate": "Format endDate tidak valid. Gunakan YYYY-MM-DD."}
            )
        attrs["end_date"] = end_date
        return attrs


class PromoImpactQuerySerializer(serializers.Serializer):
    """Validates query-params for GET /api/dashboard/membership/promo-impact."""

    startDate = serializers.CharField(required=True)
    endDate = serializers.CharField(required=True)
    compareWith = serializers.ChoiceField(
        choices=["previous_period", "previous_year"],
        required=False,
        allow_null=True,
        default=None,
    )

    def validate(self, attrs):
        start_raw = attrs.get("startDate")
        end_raw = attrs.get("endDate")

        try:
            start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"startDate": "Format startDate tidak valid. Gunakan YYYY-MM-DD."}
            )

        try:
            end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(
                {"endDate": "Format endDate tidak valid. Gunakan YYYY-MM-DD."}
            )

        if start_date > end_date:
            raise serializers.ValidationError(
                {"dateRange": "startDate tidak boleh lebih besar dari endDate."}
            )

        attrs["start_date"] = start_date
        attrs["end_date"] = end_date
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# Global Date Filter serializer  (AC 1-9)
# ─────────────────────────────────────────────────────────────────────────────

class GlobalDateFilterSerializer(DateRangeMixin, ComparisonModeMixin, serializers.Serializer):
    """
    Validates query-params for GET /api/dashboard/date-filter.

    Resolves a datePreset (or explicit startDate/endDate) and an optional
    comparisonMode into concrete date ranges, returning them to the client.
    """

    # ── Date range ────────────────────────────────────────────────────────────
    datePreset = serializers.ChoiceField(
        choices=list(VALID_PRESETS),
        required=False,
        allow_null=True,
        default=None,
    )
    startDate = serializers.CharField(required=False, allow_blank=True, default="")
    endDate = serializers.CharField(required=False, allow_blank=True, default="")

    # ── Comparison ────────────────────────────────────────────────────────────
    comparisonMode = serializers.ChoiceField(
        choices=list(VALID_COMPARISON_MODES),
        required=False,
        allow_null=True,
        default="none",
    )
    comparisonStartDate = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    comparisonEndDate = serializers.CharField(
        required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        # Normalise blank strings → None so helpers work cleanly
        for field in ("comparisonStartDate", "comparisonEndDate"):
            if not attrs.get(field):
                attrs[field] = None

        attrs = self._resolve_date_range(attrs)
        attrs = self._resolve_comparison(attrs)
        return attrs
