from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class CanManageTherapist(BasePermission):
    """
    Allow access only to internal staff with OWNER, SUPERVISOR, or ADMIN role.
    THERAPIST users cannot manage other therapists.
    """

    message = "Anda tidak memiliki izin untuk mengelola data therapist."

    # Compare with string values; user.role from DB is a string (e.g. "OWNER")
    ALLOWED_ROLES = {"OWNER", "SUPERVISOR", "ADMIN"}

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        role = getattr(user, "role", None)
        return role in self.ALLOWED_ROLES
