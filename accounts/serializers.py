from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User
from therapist.models import Therapist


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """
    Accepts username + password, validates credentials,
    and returns the authenticated user instance.
    Email is NOT used for login.
    """

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError(
                "Kredensial tidak valid atau akun tidak aktif."
            )
        attrs["user"] = user
        return attrs


# ── User representation (read-only, never exposes password) ───────────────────

class UserInfoSerializer(serializers.ModelSerializer):
    """Read-only serializer returned in API responses (e.g. login)."""

    class Meta:
        model = User
        fields = ("id", "name", "username", "role")
        read_only_fields = fields


# ── Account list ──────────────────────────────────────────────────────────────

class AccountListSerializer(serializers.ModelSerializer):
    """Read-only serializer for the account list endpoint."""

    class Meta:
        model = User
        fields = ("id", "name", "username", "email", "role", "is_active")
        read_only_fields = fields


# ── Account creation ─────────────────────────────────────────────────────────

class CreateAccountSerializer(serializers.ModelSerializer):
    """
    Handles creation of new internal-staff accounts.
    Password is write-only; hashing is done via `User.set_password()`.
    Role hierarchy validation is handled in the view / permission layer.
    """

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "name", "username", "email", "password", "role")
        read_only_fields = ("id",)

    def validate_role(self, value: str) -> str:
        """Ensure the role value is one of the accepted choices."""
        valid_roles = {choice[0] for choice in User.Role.choices}
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Role tidak valid. Harus salah satu dari: {', '.join(sorted(valid_roles))}"
            )
        return value

    def create(self, validated_data: dict) -> User:
        """Create a new user with a properly hashed password."""
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)  # Hash the password
        user.save()

        # If this is a THERAPIST account, ensure there is a matching
        # Therapist profile so the Terapis page reflects the new account.
        if user.role == User.Role.THERAPIST:
            therapist, created = Therapist.objects.get_or_create(
                email=user.email,
                defaults={
                    "name": user.name,
                    "username": user.username,
                    "no_hp": "",
                    "license_number": "",
                    "specialization": "",
                    "address": "",
                    "alamat": "",
                },
            )
            therapist.user = user
            therapist.save(update_fields=["user"])

        return user


# ── Account update ────────────────────────────────────────────────────────────

class UpdateAccountSerializer(serializers.ModelSerializer):
    """
    Handles updates to an existing internal-staff account.
    Password is optional; if provided it will be re-hashed.
    Role hierarchy validation is handled in the permission layer.
    """

    password = serializers.CharField(write_only=True, min_length=8, required=False)

    class Meta:
        model = User
        fields = ("id", "name", "username", "email", "password", "role", "is_active")
        read_only_fields = ("id",)

    def validate_username(self, value: str) -> str:
        """Ensure the new username is unique (excluding the current instance)."""
        if (
            User.objects.filter(username=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError("Username sudah digunakan.")
        return value

    def validate_email(self, value: str) -> str:
        """Ensure the new email is unique (excluding the current instance)."""
        if (
            User.objects.filter(email=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError("Email sudah digunakan.")
        return value

    def validate_role(self, value: str) -> str:
        """Ensure the role value is one of the accepted choices."""
        valid_roles = {choice[0] for choice in User.Role.choices}
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Role tidak valid. Harus salah satu dari: {', '.join(sorted(valid_roles))}"
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """
        Object-level validation:
        1. Prevent users from changing their own role.
        2. Prevent assigning a role equal to or higher than the requester's,
           except OWNER who can assign any role (including OWNER).
        """
        request = self.context.get("request")
        if request and self.instance:
            new_role = attrs.get("role")
            if new_role:
                # Rule 1: Users cannot change their own role.
                if (
                    request.user.pk == self.instance.pk
                    and new_role != self.instance.role
                ):
                    raise serializers.ValidationError(
                        {"role": "Anda tidak dapat mengubah role Anda sendiri."}
                    )

                # Rule 2: The new role must be within the requester's
                # edit hierarchy (e.g. Supervisor cannot promote to Supervisor).
                if not request.user.can_edit_role(new_role):
                    raise serializers.ValidationError(
                        {"role": "Anda tidak dapat menetapkan role yang setara atau lebih tinggi dari role Anda."}
                    )
        return attrs

    def update(self, instance: User, validated_data: dict) -> User:
        """Update user fields; re-hash password if provided."""
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()

        # Keep linked Therapist profile (if any) in sync for THERAPIST role.
        if instance.role == User.Role.THERAPIST:
            try:
                therapist = instance.therapist_profile
            except Therapist.DoesNotExist:
                therapist = None

            if therapist is None:
                therapist = Therapist.objects.filter(user=instance).first()

            if therapist:
                therapist.name = instance.name
                therapist.username = instance.username
                therapist.email = instance.email
                therapist.is_active = instance.is_active
                therapist.save(update_fields=["name", "username", "email", "is_active"])

        return instance


# ── Current-user profile update ───────────────────────────────────────────────

class CurrentUserUpdateSerializer(UpdateAccountSerializer):
    """
    Reuses all validation and update logic from UpdateAccountSerializer
    but restricts writable fields to name, username, email, and password.
    Users cannot change their own role or is_active via /me.
    """

    class Meta(UpdateAccountSerializer.Meta):
        fields = ("id", "name", "username", "email", "password")
        read_only_fields = ("id",)
