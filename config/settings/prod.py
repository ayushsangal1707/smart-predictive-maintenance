import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa

DEBUG = False

# ---------------------------------------------------------------------------
# Fail loudly on insecure defaults, rather than silently deploying with them.
# A missing SECRET_KEY or DB password in production is a configuration bug,
# not something to paper over with dev.py's placeholder values.
# ---------------------------------------------------------------------------
if SECRET_KEY == "django-insecure-change-me-in-.env":  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is not set (or still the insecure default). "
        "Set a unique, random value in your production .env before deploying."
    )

if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production (comma-separated).")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

# Real SMTP backend is inherited from base.py so forgot-password emails and
# alert emails (Prompt 9) are actually delivered in production.

# ---------------------------------------------------------------------------
# Static files: served directly by the app via WhiteNoise, so a separate
# nginx/CDN static-file config isn't required to get a working deployment
# (though fronting with nginx/a CDN is still recommended at real scale —
# see DEPLOYMENT.md).
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
] + [m for m in MIDDLEWARE if m != "django.middleware.security.SecurityMiddleware"]  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Transport & cookie security
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Trust the X-Forwarded-Proto header from a reverse proxy (nginx/Docker/
# load balancer) so Django correctly knows the original request was HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Caching (used by dashboard/services.py to avoid recomputing expensive
# aggregates on every request — see the Optimization notes in Prompt 10).
# Defaults to Django's local-memory cache, which is fine for a single-
# process deployment; swap to Redis/Memcached (via CACHE_URL) once running
# multiple worker processes, so cache entries are shared across them.
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "smart-maintenance-cache",
    }
}

# ---------------------------------------------------------------------------
# Logging: errors go to stdout/stderr (captured by Docker/systemd/your
# platform's log aggregator) rather than a local file, which containers
# generally shouldn't rely on for persistence.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
