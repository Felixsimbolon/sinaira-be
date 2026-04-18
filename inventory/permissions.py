from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwnerRole(BasePermission):
    """
    Role yang boleh mengelola inventori: OWNER, SUPERVISOR, ADMIN.
    THERAPIST → 403.

    Nama class dipertahankan (historis) agar tidak memecah import lain,
    tetapi cakupan role sudah diperluas sesuai kebutuhan bisnis baru.
    """

    message = "Hanya OWNER, SUPERVISOR, atau ADMIN yang dapat mengelola inventori."

    ALLOWED_ROLES = {"OWNER", "SUPERVISOR", "ADMIN"}

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) in self.ALLOWED_ROLES


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

