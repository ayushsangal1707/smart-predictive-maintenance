"""
core/email_utils.py
---------------------
Thin wrapper around Django's send_mail(), used for the "Email Alerts"
feature: real emails (not just in-app notifications) for the events that
matter most — a maintenance assignment, and a Critical-risk prediction.

Respects each user's `UserPreference.email_notifications_enabled` flag
(see accounts/models.py) so people can opt out of email without losing the
in-app notification.

Uses fail_silently=True: a broken SMTP config shouldn't turn a successful
in-app action (assigning an engineer, running a prediction) into a 500
error for the user — the in-app Notification is the reliable channel;
email is a best-effort addition on top of it.
"""

from django.conf import settings
from django.core.mail import send_mail


def send_alert_email(user, subject, message):
    if user is None or not user.email:
        return False

    preference = getattr(user, "preference", None)
    if preference is not None and not preference.email_notifications_enabled:
        return False

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    return True
