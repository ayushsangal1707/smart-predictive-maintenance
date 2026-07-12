from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.constants import (
    DEPARTMENT_CHOICES,
    MACHINE_STATUS_CHOICES,
    MACHINE_TYPE_CHOICES,
    STATUS_ACTIVE,
)


def validate_not_future_date(value):
    """Installation date can't be in the future — a machine can't be
    installed on a date that hasn't happened yet."""
    if value > timezone.localdate():
        raise ValidationError("Installation date cannot be in the future.")


class Machine(models.Model):
    """
    Represents a single piece of BHEL plant equipment being tracked for
    predictive maintenance. Referred to as "Equipment" in the Prompt 1
    architecture/database-schema (table `equipment_equipment`) and as
    "Machine" in this module's UI/naming, per this prompt's wording —
    same model, both terms used interchangeably in the project docs.
    """

    machine_code = models.CharField(
        max_length=30,
        unique=True,
        help_text="Unique asset tag / identifier, e.g. BHEL-TUR-001",
    )
    name = models.CharField(max_length=150)
    machine_type = models.CharField(max_length=30, choices=MACHINE_TYPE_CHOICES, default="OTHER")
    department = models.CharField(max_length=30, choices=DEPARTMENT_CHOICES, default="OTHER")
    location = models.CharField(max_length=150, blank=True, help_text="Physical location / plant bay / floor")
    manufacturer = models.CharField(max_length=150, blank=True)
    installation_date = models.DateField(validators=[validate_not_future_date])
    status = models.CharField(max_length=20, choices=MACHINE_STATUS_CHOICES, default=STATUS_ACTIVE)
    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="machines_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department"]),
            models.Index(fields=["machine_type"]),
        ]

    def __str__(self):
        return f"{self.machine_code} - {self.name}"

    def get_absolute_url(self):
        return reverse("equipment:detail", kwargs={"pk": self.pk})

    @property
    def status_badge_class(self):
        from core.constants import MACHINE_STATUS_BADGE_CLASS
        return MACHINE_STATUS_BADGE_CLASS.get(self.status, "bg-secondary")

    @property
    def age_in_days(self):
        return (timezone.localdate() - self.installation_date).days
