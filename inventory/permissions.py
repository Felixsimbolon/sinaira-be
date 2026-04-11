from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwnerRole(BasePermission):
    """
    Hanya role OWNER yang boleh mengakses endpoint inventori.
    SUPERVISOR, ADMIN, THERAPIST → 403.
    """

    message = "Hanya pemilik (OWNER) yang dapat mengelola inventori."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) == "OWNER"
