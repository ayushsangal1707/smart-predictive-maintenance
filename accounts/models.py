from django.conf import settings
from django.db import models

from core.constants import ROLE_CHOICES, ROLE_ENGINEER


class UserProfile(models.Model):
    """
    Extends the built-in auth.User with role and BHEL-specific fields,
    rather than swapping in a custom AUTH_USER_MODEL. This keeps
    django.contrib.auth (admin, permissions, password reset) working
    out of the box while still letting us attach whatever fields the
    project needs.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_ENGINEER,
        help_text="Controls what the user can see and do across the system.",
    )
    employee_id = models.CharField(max_length=30, blank=True)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def is_admin(self):
        from core.constants import ROLE_ADMIN
        return self.role == ROLE_ADMIN

    @property
    def is_engineer(self):
        return self.role == ROLE_ENGINEER

    @property
    def is_manager(self):
        from core.constants import ROLE_MANAGER
        return self.role == ROLE_MANAGER


class UserPreference(models.Model):
    """
    Lightweight per-user settings, separate from UserProfile (which holds
    identity/role fields) so the Settings page can be a plain, focused
    form without touching role/employee data.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preference",
    )
    dark_mode_default = models.BooleanField(
        default=False,
        help_text="Theme to use when this browser has no saved preference yet.",
    )
    email_notifications_enabled = models.BooleanField(
        default=True,
        help_text="Receive email alerts (maintenance assignments, critical risk predictions) in addition to in-app notifications.",
    )

    def __str__(self):
        return f"Preferences for {self.user.get_username()}"
