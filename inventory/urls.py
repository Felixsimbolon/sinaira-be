from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InventoryViewSet, TherapistSupplyAssignmentViewSet

router = DefaultRouter()
router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(
    r"therapist-supply-assignments",
    TherapistSupplyAssignmentViewSet,
    basename="therapist-supply-assignment",
)

urlpatterns = [
    path("", include(router.urls)),
]

