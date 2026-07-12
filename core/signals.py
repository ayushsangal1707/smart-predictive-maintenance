from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .audit import log_activity
from .models import ACTION_LOGIN, ACTION_LOGOUT


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    log_activity(user, ACTION_LOGIN, request=request)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    # `user` can be None if the session had already expired.
    log_activity(user, ACTION_LOGOUT, request=request)
