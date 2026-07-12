from .base import *  # noqa

DEBUG = True

# Print password-reset / activation emails to the console instead of
# actually sending them while developing locally.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1"]
