from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsAdminOrSupervisorOrOwner(BasePermission):
    """
    Permission that allows access only to users with roles:
    - OWNER
    - SUPERVISOR
    - ADMIN
    
    Used for booking management views.
    """

    message = "Anda tidak memiliki akses."

    def has_permission(self, request: Request, view: APIView) -> bool:
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has the required role
        allowed_roles = ['OWNER', 'SUPERVISOR', 'ADMIN']
        return hasattr(request.user, 'role') and request.user.role in allowed_roles
