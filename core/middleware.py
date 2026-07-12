class RoleAccessMiddleware:
    """
    Attaches `request.role` (a plain string, e.g. "ADMIN") for authenticated
    users so templates and views can branch on role without repeatedly
    joining to UserProfile. Anonymous users get `request.role = None`.

    This does NOT enforce access control by itself — per-view restriction is
    done with the `@role_required(...)` decorator in accounts/decorators.py.
    Keeping the two concerns separate means this middleware stays simple and
    safe to run globally, while access rules stay explicit and visible on
    each view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.role = None
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile is not None:
                request.role = profile.role
        return self.get_response(request)
