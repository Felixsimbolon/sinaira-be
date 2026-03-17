from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LayananKategoriViewSet, LayananViewSet

router = DefaultRouter()
router.register(r"layanan-kategori", LayananKategoriViewSet, basename="layanan-kategori")
router.register(r"layanan", LayananViewSet, basename="layanan")

urlpatterns = [
    path("", include(router.urls)),
]
