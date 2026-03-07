from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class CanCreateAccount(BasePermission):
    """
    RBAC permission that enforces the role-hierarchy rules for account
    creation.

    Hierarchy
    ---------
    OWNER       → can create SUPERVISOR, ADMIN, THERAPIST
    SUPERVISOR  → can create ADMIN, THERAPIST
    ADMIN       → can create THERAPIST
    THERAPIST   → cannot create any account

    If a user tries to create an account with the same or higher role,
    the API returns **403 Forbidden**.
    """

    message = "Anda tidak memiliki izin untuk membuat akun dengan role ini."

    def has_permission(self, request: Request, view: APIView) -> bool:
        # Only applies to POST (account-creation) requests.
        if request.method != "POST":
            return True

        # Must be authenticated.
        if not request.user or not request.user.is_authenticated:
            return False

        target_role = request.data.get("role", "")
        return request.user.can_create_role(target_role)


class CanEditAccount(BasePermission):
    """
    Object-level RBAC permission for editing accounts.

    Rules:
        1. A user can **always** edit their own account (self-edit).
        2. OWNER       → can edit OWNER, SUPERVISOR, ADMIN, THERAPIST
        3. SUPERVISOR  → can edit ADMIN, THERAPIST
        4. ADMIN       → can edit THERAPIST
        5. THERAPIST   → can only edit themselves

    Returns **403 Forbidden** if the requesting user tries to edit an
    account they are not permitted to modify.
    """

    message = "Anda tidak memiliki izin untuk mengedit akun ini."

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        # Rule 1: Users can always edit their own account.
        if request.user.pk == obj.pk:
            return True

        # Rules 2-5: Check role hierarchy for editing other accounts.
        return request.user.can_edit_role(obj.role)
