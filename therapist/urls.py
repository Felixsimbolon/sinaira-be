from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminTherapistDateOverrideDetailView,
    AdminTherapistDateOverrideView,
    AdminTherapistGeocodeView,
    AdminTherapistTimetableView,
    AdminTherapistWeeklyScheduleDetailView,
    AdminTherapistWeeklyScheduleView,
    TherapistViewSet,
)

router = DefaultRouter()
router.register(r"therapists", TherapistViewSet, basename="therapist")

urlpatterns = [
    path("admin/therapists/<int:id>/geocode/", AdminTherapistGeocodeView.as_view(), name="admin-therapist-geocode"),
    path("admin/therapists/<int:id>/weekly-schedule/", AdminTherapistWeeklyScheduleView.as_view(), name="admin-therapist-weekly-schedule"),
    path("admin/therapists/<int:id>/weekly-schedule/<int:slot_id>/", AdminTherapistWeeklyScheduleDetailView.as_view(), name="admin-therapist-weekly-schedule-detail"),
    path("admin/therapists/<int:id>/date-overrides/", AdminTherapistDateOverrideView.as_view(), name="admin-therapist-date-overrides"),
    path("admin/therapists/<int:id>/date-overrides/<int:override_id>/", AdminTherapistDateOverrideDetailView.as_view(), name="admin-therapist-date-override-detail"),
    path("admin/therapists/<int:id>/timetable/", AdminTherapistTimetableView.as_view(), name="admin-therapist-timetable"),
    path("", include(router.urls)),
]