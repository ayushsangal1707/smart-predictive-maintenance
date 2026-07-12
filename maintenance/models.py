from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from equipment.models import Machine
from predictions.models import Prediction

STATUS_OPEN = "OPEN"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_ON_HOLD = "ON_HOLD"
STATUS_COMPLETED = "COMPLETED"
STATUS_CANCELLED = "CANCELLED"

STATUS_CHOICES = [
    (STATUS_OPEN, "Open"),
    (STATUS_ASSIGNED, "Assigned"),
    (STATUS_IN_PROGRESS, "In Progress"),
    (STATUS_ON_HOLD, "On Hold"),
    (STATUS_COMPLETED, "Completed"),
    (STATUS_CANCELLED, "Cancelled"),
]

STATUS_BADGE_CLASS = {
    STATUS_OPEN: "bg-secondary",
    STATUS_ASSIGNED: "bg-info text-dark",
    STATUS_IN_PROGRESS: "bg-primary",
    STATUS_ON_HOLD: "bg-warning text-dark",
    STATUS_COMPLETED: "bg-success",
    STATUS_CANCELLED: "bg-dark",
}

# Open statuses that still require attention — used by dashboard cards and
# by "overdue" calculations (a COMPLETED/CANCELLED request can't be overdue).
OPEN_STATUSES = [STATUS_OPEN, STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_ON_HOLD]

PRIORITY_LOW = "LOW"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_HIGH = "HIGH"
PRIORITY_CRITICAL = "CRITICAL"

PRIORITY_CHOICES = [
    (PRIORITY_LOW, "Low"),
    (PRIORITY_MEDIUM, "Medium"),
    (PRIORITY_HIGH, "High"),
    (PRIORITY_CRITICAL, "Critical"),
]

PRIORITY_BADGE_CLASS = {
    PRIORITY_LOW: "bg-success",
    PRIORITY_MEDIUM: "bg-info text-dark",
    PRIORITY_HIGH: "bg-warning text-dark",
    PRIORITY_CRITICAL: "bg-danger",
}


class MaintenanceRequest(models.Model):
    """
    A single maintenance job for a machine — either raised manually by an
    Engineer/Manager, or created directly from a High/Critical-risk
    Prediction (see predictions app, Prompt 6) via the "Create Maintenance
    Request" action on that prediction's detail page.
    """

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="maintenance_requests")
    source_prediction = models.ForeignKey(
        Prediction, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_requests",
        help_text="If this request was raised from a prediction alert, the prediction it came from.",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="maintenance_requests_raised"
    )
    assigned_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="maintenance_requests_assigned",
    )

    scheduled_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["machine", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title} — {self.machine.machine_code}"

    def get_absolute_url(self):
        return reverse("maintenance:detail", kwargs={"pk": self.pk})

    def clean(self):
        if self.scheduled_date and self.completed_at and self.scheduled_date > self.completed_at:
            raise ValidationError("Scheduled date cannot be after the completion date.")

    @property
    def status_badge_class(self):
        return STATUS_BADGE_CLASS.get(self.status, "bg-secondary")

    @property
    def priority_badge_class(self):
        return PRIORITY_BADGE_CLASS.get(self.priority, "bg-secondary")

    @property
    def is_overdue(self):
        return (
            self.status in OPEN_STATUSES
            and self.scheduled_date is not None
            and self.scheduled_date < timezone.now()
        )


class StatusHistory(models.Model):
    """
    Full audit trail of every status transition on a request — separate
    from Comment (free-text discussion) so the two timelines (facts vs.
    conversation) can be told apart, but both are merged chronologically
    on the request detail page's "History" timeline.
    """

    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="status_history")
    old_status = models.CharField(max_length=15, choices=STATUS_CHOICES, blank=True)
    new_status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at"]
        verbose_name_plural = "Status histories"

    def __str__(self):
        return f"{self.request_id}: {self.old_status or '—'} -> {self.new_status}"


class Comment(models.Model):
    """A single comment on a maintenance request, visible to anyone who can view the request."""

    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on request #{self.request_id}"


class Notification(models.Model):
    """
    Simple in-app notification, created whenever a maintenance request is
    assigned, its status changes, or a new comment is added — always
    targeted to whichever *other* user is affected (the actor never
    notifies themselves).
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"To {self.user}: {self.message}"
