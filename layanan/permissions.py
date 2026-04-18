from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.request import Request
from rest_framework.views import APIView


class LayananPermission(BasePermission):
    """
    - Semua user dapat lihat daftar/detail (GET, HEAD, OPTIONS)
    - CREATE/UPDATE/DELETE hanya OWNER, SUPERVISOR
    """

    message = "Anda tidak memiliki akses."
    ALLOWED_ROLES = {"OWNER", "SUPERVISOR"}

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        return getattr(user, "role", None) in self.ALLOWED_ROLES
