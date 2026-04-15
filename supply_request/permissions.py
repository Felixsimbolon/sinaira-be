from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsTherapistRole(BasePermission):
    message = "Hanya role THERAPIST yang dapat membuat supply request."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) == "THERAPIST"


class IsSupervisorRole(BasePermission):
    message = "Hanya role SUPERVISOR yang dapat memproses supply request."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) == "SUPERVISOR"
