from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LayananViewSet

router = DefaultRouter()
router.register(r"layanan", LayananViewSet, basename="layanan")

urlpatterns = [
    path("", include(router.urls)),
]
