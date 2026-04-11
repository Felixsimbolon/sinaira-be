from django.urls import path

from .views import (
    MySupplyRequestListView,
    SupplyRequestCollectionView,
    SupplyRequestDetailView,
    SupplyRequestItemOptionListView,
)

app_name = "supply_request"

urlpatterns = [
    path("supply-request/items", SupplyRequestItemOptionListView.as_view(), name="supply-request-items"),
    path(
        "supply-request/items/",
        SupplyRequestItemOptionListView.as_view(),
        name="supply-request-items-slash",
    ),
    path("supply-request/me", MySupplyRequestListView.as_view(), name="supply-request-me"),
    path("supply-request/me/", MySupplyRequestListView.as_view(), name="supply-request-me-slash"),
    path("supply-request", SupplyRequestCollectionView.as_view(), name="supply-request-collection"),
    path("supply-request/", SupplyRequestCollectionView.as_view(), name="supply-request-collection-slash"),
    path("supply-request/<int:id>", SupplyRequestDetailView.as_view(), name="supply-request-detail"),
    path("supply-request/<int:id>/", SupplyRequestDetailView.as_view(), name="supply-request-detail-slash"),
]
