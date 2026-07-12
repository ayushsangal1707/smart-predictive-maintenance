"""
core/audit.py
--------------
Call `log_activity()` directly from views right after a create/update/
delete/prediction/export action. Kept as an explicit call (not a signal)
so the acting user is always correctly attributed — see the design note
in core/models.py.
"""

from .models import AuditLog


def _get_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_activity(user, action, obj=None, description="", request=None):
    """
    Records one audit/activity entry.

    Args:
        user: the acting user (or None for system/anonymous actions)
        action: one of core.models.ACTION_* constants
        obj: the model instance the action was performed on (optional —
             its class name, pk, and str() are captured automatically)
        description: free-text detail (e.g. "Exported machines to CSV")
        request: the current HttpRequest, if available, to capture IP
    """
    return AuditLog.objects.create(
        user=user,
        action=action,
        model_name=obj.__class__.__name__ if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk else "",
        object_repr=str(obj) if obj is not None else "",
        description=description,
        ip_address=_get_ip(request),
    )
