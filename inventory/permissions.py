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


class IsOwnerOrSupervisor(BasePermission):
    """
    Hanya role OWNER dan SUPERVISOR yang boleh mengakses endpoint
    therapist supply assignment.
    """

    message = "Hanya OWNER atau SUPERVISOR yang dapat mengelola assignment bahan."

    ALLOWED_ROLES = {"OWNER", "SUPERVISOR"}

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) in self.ALLOWED_ROLES

