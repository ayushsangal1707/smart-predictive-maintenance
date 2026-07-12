from django.conf import settings
from django.db import models

ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_DELETE = "DELETE"
ACTION_LOGIN = "LOGIN"
ACTION_LOGOUT = "LOGOUT"
ACTION_PREDICT = "PREDICT"
ACTION_EXPORT = "EXPORT"
ACTION_OTHER = "OTHER"

ACTION_CHOICES = [
    (ACTION_CREATE, "Create"),
    (ACTION_UPDATE, "Update"),
    (ACTION_DELETE, "Delete"),
    (ACTION_LOGIN, "Login"),
    (ACTION_LOGOUT, "Logout"),
    (ACTION_PREDICT, "Prediction Run"),
    (ACTION_EXPORT, "Report Export"),
    (ACTION_OTHER, "Other"),
]


class AuditLog(models.Model):
    """
    Unified activity/audit trail for the whole project. Serves both roles
    the prompt asks for: a lightweight "what's been happening" activity
    feed, and a more formal audit record (who, what, when, from which IP)
    for compliance/security review — rather than maintaining two separate
    overlapping logs.

    Entries are created explicitly from views (log_activity(), see
    core/audit.py) for CRUD-style actions so the acting user is always
    correctly attributed — Django model signals (post_save/post_delete)
    don't carry the request/user, so relying on them here would produce
    audit entries with no reliable "who". LOGIN/LOGOUT are the one
    exception: Django's auth signals do pass the request, so those are
    wired via signals in core/signals.py.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["model_name"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        who = self.user or "Anonymous"
        return f"{who} — {self.get_action_display()} {self.model_name} {self.object_repr}".strip()
