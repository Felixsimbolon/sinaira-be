from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InventoryViewSet, SupplyTrackerView, TherapistSupplyAssignmentViewSet

router = DefaultRouter()
router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(
    r"therapist-supply-assignments",
    TherapistSupplyAssignmentViewSet,
    basename="therapist-supply-assignment",
)

urlpatterns = [
    path("supply-tracker/", SupplyTrackerView.as_view(), name="supply-tracker"),
    path("", include(router.urls)),
]
