from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsAuthenticatedUser(BasePermission):
    """
    Allows access only to authenticated users.
    Returns 401 for anonymous requests.
    """

    message = "Autentikasi diperlukan untuk mengakses resource ini."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)


class IsSupervisorOrOwner(BasePermission):
    """
    Allows access only to users with SUPERVISOR or OWNER role.
    """

    message = "Hanya Supervisor atau Owner yang dapat mengakses data review."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        allowed_roles = {"SUPERVISOR", "OWNER"}
        return hasattr(request.user, "role") and request.user.role in allowed_roles
