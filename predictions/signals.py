from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.email_utils import send_alert_email

from .models import Prediction


@receiver(post_save, sender=Prediction)
def email_admins_on_critical_prediction(sender, instance, created, **kwargs):
    """
    Sends an email alert to every Admin the moment a new Prediction comes
    back Critical risk — this is the one prediction outcome urgent enough
    to warrant proactively emailing people rather than waiting for them to
    check the dashboard.
    """
    if not created or instance.risk_level != "CRITICAL":
        return

    admins = User.objects.filter(profile__role="ADMIN")
    subject = f"CRITICAL risk alert: {instance.machine.name}"
    message = (
        f"A new prediction for {instance.machine.name} ({instance.machine.machine_code}) "
        f"came back CRITICAL risk.\n\n"
        f"Failure probability: {instance.failure_probability:.0%}\n"
        f"Predicted at: {instance.predicted_at:%Y-%m-%d %H:%M}\n\n"
        f"Please review and schedule maintenance as needed."
    )
    for admin in admins:
        send_alert_email(admin, subject, message)
