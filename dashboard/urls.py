from django.urls import path

from .views import TherapistPerformanceSummaryView

app_name = "dashboard"

urlpatterns = [
    path(
        "dashboard/therapist/performance-summary",
        TherapistPerformanceSummaryView.as_view(),
        name="therapist-performance-summary",
    ),
]
