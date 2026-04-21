from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryViewSet,
    SupplyTrackerView,
    TherapistSupplyAssignmentViewSet,
    InventoryAssignmentInactiveThresholdView,
)

router = DefaultRouter()
router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(
    r"therapist-supply-assignments",
    TherapistSupplyAssignmentViewSet,
    basename="therapist-supply-assignment",
)

urlpatterns = [
    path("supply-tracker/", SupplyTrackerView.as_view(), name="supply-tracker"),
    path(
        "inventory/<int:item_id>/assignment-inactive-threshold/",
        InventoryAssignmentInactiveThresholdView.as_view(),
        name="inventory-assignment-inactive-threshold",
    ),
    path("", include(router.urls)),
]
