from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model for internal staff accounts.
    Extends Django's AbstractUser; uses **username** as the login identifier.
    Customers do NOT have accounts — only the four internal roles below.
    """

    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        ADMIN = "ADMIN", "Admin"
        THERAPIST = "THERAPIST", "Therapist"

    # ── Role hierarchy map (for account CREATION) ─────────────────────
    # Maps each role to the set of roles it is allowed to create.
    ROLE_HIERARCHY: dict[str, set[str]] = {
        Role.OWNER: {Role.SUPERVISOR, Role.ADMIN, Role.THERAPIST},
        Role.SUPERVISOR: {Role.ADMIN, Role.THERAPIST},
        Role.ADMIN: {Role.THERAPIST},
        Role.THERAPIST: set(),  # Therapists cannot create any accounts
    }

    # ── Edit hierarchy map (for account UPDATE) ───────────────────────
    # OWNER can edit all roles including other OWNERs.
    # Self-edit is handled separately in the permission class.
    EDIT_HIERARCHY: dict[str, set[str]] = {
        Role.OWNER: {Role.OWNER, Role.SUPERVISOR, Role.ADMIN, Role.THERAPIST},
        Role.SUPERVISOR: {Role.ADMIN, Role.THERAPIST},
        Role.ADMIN: {Role.THERAPIST},
        Role.THERAPIST: set(),
    }

    name = models.CharField(
        max_length=255,
        help_text="Full display name of the staff member.",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.THERAPIST,
        help_text="Internal staff role determining permissions.",
    )

    # ── Keep username as the sole login field ─────────────────────────
    # (AbstractUser already sets USERNAME_FIELD = "username")
    # email is stored but NOT used for authentication.
    email = models.EmailField(unique=True, help_text="Must be unique.")

    class Meta:
        ordering = ["username"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    # ── Helper methods ────────────────────────────────────────────────
    def can_create_role(self, target_role: str) -> bool:
        """Return True if this user's role is allowed to create *target_role*."""
        allowed = self.ROLE_HIERARCHY.get(self.role, set())
        return target_role in allowed

    def can_edit_role(self, target_role: str) -> bool:
        """Return True if this user's role is allowed to edit a user with *target_role*."""
        allowed = self.EDIT_HIERARCHY.get(self.role, set())
        return target_role in allowed
