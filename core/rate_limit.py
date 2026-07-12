"""
core/rate_limit.py
--------------------
A minimal cache-based request throttle — no extra dependency needed since
Django's cache framework already does the heavy lifting. Used on the
login, registration, and password-reset views (all unauthenticated-facing,
so all realistic brute-force/spam targets).

Not a replacement for a dedicated WAF/rate-limiting layer at real scale,
but meaningfully raises the cost of a brute-force attempt against a
single-server deployment, which is the deployment target this project is
built for.
"""

from django.core.cache import cache
from django.http import HttpResponse


def rate_limit(key_prefix, max_attempts=5, window_seconds=300):
    """
    Decorator for a view: allows at most `max_attempts` POSTs from the same
    IP within `window_seconds`, keyed by `key_prefix` (so login and
    password-reset throttles don't share a bucket). GET requests are never
    throttled — only state-changing attempts count.
    """

    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if request.method == "POST":
                ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown"))
                ip = ip.split(",")[0].strip()
                cache_key = f"ratelimit:{key_prefix}:{ip}"
                attempts = cache.get(cache_key, 0)
                if attempts >= max_attempts:
                    return HttpResponse(
                        "Too many attempts. Please wait a few minutes before trying again.",
                        status=429,
                    )
                cache.set(cache_key, attempts + 1, timeout=window_seconds)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
