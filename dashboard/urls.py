from django.urls import path

from .views import (
    AtRiskCustomerView,
    CohortRetentionView,
    GlobalDateFilterView,
    KPIAggregationView,
    PromoImpactView,
    TherapistPerformanceSummaryView,
)

app_name = "dashboard"

urlpatterns = [
    path(
        "dashboard/therapist/performance-summary",
        TherapistPerformanceSummaryView.as_view(),
        name="therapist-performance-summary",
    ),
    path(
        "dashboard/kpi",
        KPIAggregationView.as_view(),
        name="kpi-aggregation",
    ),
    path(
        "dashboard/membership/cohort",
        CohortRetentionView.as_view(),
        name="membership-cohort",
    ),
    path(
        "dashboard/membership/at-risk",
        AtRiskCustomerView.as_view(),
        name="membership-at-risk",
    ),
    path(
        "dashboard/membership/promo-impact",
        PromoImpactView.as_view(),
        name="membership-promo-impact",
    ),
    path(
        "dashboard/date-filter",
        GlobalDateFilterView.as_view(),
        name="dashboard-date-filter",
    ),
]

