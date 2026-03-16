from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AdminTherapistGeocodeView, TherapistViewSet

router = DefaultRouter()
router.register(r"therapists", TherapistViewSet, basename="therapist")

urlpatterns = [
    path("admin/therapists/<int:id>/geocode/", AdminTherapistGeocodeView.as_view(), name="admin-therapist-geocode"),
    path("", include(router.urls)),
]