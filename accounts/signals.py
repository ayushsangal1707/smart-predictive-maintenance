from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.constants import ROLE_ADMIN
from .models import UserPreference, UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    """
    Guarantees every auth.User always has exactly one UserProfile and one
    UserPreference, even for users created outside the registration view
    (e.g. via `createsuperuser` or the Django admin). Without this,
    `request.user.profile` / `request.user.preference` could raise
    DoesNotExist for admin-created accounts.

    Superusers default to the ADMIN role (rather than the normal ENGINEER
    default) since anyone created via `createsuperuser` is, by definition,
    meant to have full system access.
    """
    if created:
        default_role = ROLE_ADMIN if instance.is_superuser else None
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        if default_role:
            profile.role = default_role
            profile.save()
        UserPreference.objects.get_or_create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)
        UserPreference.objects.get_or_create(user=instance)
