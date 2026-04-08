from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwnerOnly(BasePermission):
    """Allow access only for authenticated OWNER users."""

    message = "Hanya Owner yang dapat mengakses endpoint admin promo/event."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "OWNER"


PublicReadPermission = AllowAny
