from django.urls import path

from .views import (
    AdminPromoArchiveView,
    AdminPromoDetailView,
    AdminPromoListCreateView,
    AdminPromoUnarchiveView,
    PublicPromoDetailView,
    PublicPromoListView,
)

app_name = "event"

urlpatterns = [
    path("admin/promos", AdminPromoListCreateView.as_view(), name="admin-promo-list-create"),
    path("admin/promos/<int:pk>", AdminPromoDetailView.as_view(), name="admin-promo-detail"),
    path("admin/promos/<int:pk>/archive", AdminPromoArchiveView.as_view(), name="admin-promo-archive"),
    path("admin/promos/<int:pk>/unarchive", AdminPromoUnarchiveView.as_view(), name="admin-promo-unarchive"),
    path("promos", PublicPromoListView.as_view(), name="public-promo-list"),
    path("promos/<int:pk>", PublicPromoDetailView.as_view(), name="public-promo-detail"),
]
