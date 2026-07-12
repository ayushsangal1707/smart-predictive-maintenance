from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*allowed_roles):
    """
    Restricts a view to users whose UserProfile.role is in `allowed_roles`.

    Usage:
        @role_required(ROLE_ADMIN)
        def retrain_model(request): ...

        @role_required(ROLE_ADMIN, ROLE_MANAGER)
        def view_reports(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if profile is None or profile.role not in allowed_roles:
                messages.error(request, "You don't have permission to access that page.")
                return redirect("accounts:profile")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
