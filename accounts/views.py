from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import CanCreateAccount, CanEditAccount
from .serializers import (
    AccountListSerializer,
    CreateAccountSerializer,
    CurrentUserUpdateSerializer,
    LoginSerializer,
    UpdateAccountSerializer,
    UserInfoSerializer,
)


# ── POST /api/auth/login/ ────────────────────────────────────────────────────

class LoginView(APIView):
    """
    Authenticate with **username + password** and receive JWT tokens
    together with basic user information.

    Returns 401 if credentials are invalid or the account is inactive.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(
                {"detail": "Kredensial tidak valid."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user: User = serializer.validated_data["user"]

        # Generate JWT token pair
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserInfoSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# ── GET & POST /api/accounts/ ─────────────────────────────────────────────────

class AccountListCreateView(APIView):
    """
    GET  → List users visible to the requesting user (role-filtered).
    POST → Create a new internal-staff account (role-hierarchy enforced).

    * Requires JWT authentication for both methods.
    * CanCreateAccount permission only enforces on POST; GET passes through.

    Status codes:
        200 – user list returned           (GET)
        201 – account created              (POST)
        400 – validation error             (POST)
        401 – not authenticated            (GET / POST)
        403 – role hierarchy violation      (POST)
    """

    permission_classes = [IsAuthenticated, CanCreateAccount]

    # ── Role visibility rules ─────────────────────────────────────────
    # Defines which roles each role is allowed to see.
    ROLE_VISIBILITY: dict[str, list[str]] = {
        User.Role.OWNER: [
            User.Role.OWNER,
            User.Role.SUPERVISOR,
            User.Role.ADMIN,
            User.Role.THERAPIST,
        ],
        User.Role.SUPERVISOR: [User.Role.ADMIN, User.Role.THERAPIST],
        User.Role.ADMIN: [User.Role.THERAPIST],
        User.Role.THERAPIST: [],  # No visibility below therapist
    }

    # ── GET: list accounts ────────────────────────────────────────────
    def get(self, request: Request) -> Response:
        visible_roles = self.ROLE_VISIBILITY.get(request.user.role, [])
        users = User.objects.filter(role__in=visible_roles)
        serializer = AccountListSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ── POST: create account ──────────────────────────────────────────
    def post(self, request: Request) -> Response:
        serializer = CreateAccountSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        return Response(
            UserInfoSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


# ── PUT /api/accounts/{id}/ ───────────────────────────────────────────────────

class AccountDetailView(APIView):
    """
    PUT → Update an existing internal-staff account.

    * Requires JWT authentication.
    * Enforces role-hierarchy: users can only edit accounts with a
      strictly lower role.

    Status codes:
        200 – account updated
        400 – validation error (duplicate username/email, invalid data)
        401 – not authenticated
        403 – role hierarchy violation
        404 – user not found
    """

    permission_classes = [IsAuthenticated, CanEditAccount]

    def get_object(self, pk: int) -> User:
        """Retrieve the target user or raise 404."""
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def put(self, request: Request, pk: int) -> Response:
        user = self.get_object(pk)
        if user is None:
            return Response(
                {"detail": "Pengguna tidak ditemukan."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check object-level permission (role hierarchy)
        self.check_object_permissions(request, user)

        serializer = UpdateAccountSerializer(
            user, data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_user = serializer.save()

        return Response(
            AccountListSerializer(updated_user).data,
            status=status.HTTP_200_OK,
        )


# ── GET & PUT /api/accounts/me/ ───────────────────────────────────────────────

class CurrentUserView(APIView):
    """
    GET  → Return the profile of the currently authenticated user.
    PUT  → Update the current user's own profile (name, username, email,
           password only — role and is_active cannot be changed).

    Status codes:
        200 – profile returned / updated
        400 – validation error (duplicate username/email)
        401 – not authenticated
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = AccountListSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request: Request) -> Response:
        serializer = CurrentUserUpdateSerializer(
            request.user,
            data=request.data,
            context={"request": request},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_user = serializer.save()

        return Response(
            AccountListSerializer(updated_user).data,
            status=status.HTTP_200_OK,
        )
