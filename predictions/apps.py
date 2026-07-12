from django.apps import AppConfig


class PredictionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "predictions"
    verbose_name = "Predictive Maintenance"

    def ready(self):
        import predictions.signals  # noqa: F401
