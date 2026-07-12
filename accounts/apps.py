from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Registers the post_save signal that auto-creates a UserProfile
        # whenever an auth.User is created (see accounts/signals.py).
        import accounts.signals  # noqa: F401
