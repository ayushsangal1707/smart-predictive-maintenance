from django.conf import settings
from django.db import models

from equipment.models import Machine

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"

RISK_CHOICES = [
    (RISK_LOW, "Low"),
    (RISK_MEDIUM, "Medium"),
    (RISK_HIGH, "High"),
    (RISK_CRITICAL, "Critical"),
]

RISK_BADGE_CLASS = {
    RISK_LOW: "bg-success",
    RISK_MEDIUM: "bg-info text-dark",
    RISK_HIGH: "bg-warning text-dark",
    RISK_CRITICAL: "bg-danger",
}


def risk_level_for_probability(probability: float) -> str:
    """
    Maps a model's failure probability (0-1) to a human-facing risk band.
    Kept as a plain function (not a model method) so predict.py can use the
    same thresholds when building the response for the JSON API, without
    needing a saved Prediction instance yet.
    """
    if probability >= 0.75:
        return RISK_CRITICAL
    if probability >= 0.5:
        return RISK_HIGH
    if probability >= 0.25:
        return RISK_MEDIUM
    return RISK_LOW


class ModelVersion(models.Model):
    """
    Metadata for one trained model artifact saved by predictions/ml/train.py
    (see model_registry/model_<version>_metadata.json, which this model
    mirrors in the database so the Django app can query "which model is
    currently active" without reading JSON files at request time).
    """

    version_name = models.CharField(max_length=30, unique=True)
    algorithm = models.CharField(max_length=100)
    trained_at = models.DateTimeField()
    file_path = models.CharField(max_length=255, help_text="Path to the .pkl file, relative to predictions/ml/model_registry/")
    feature_columns = models.JSONField(default=list)
    metrics = models.JSONField(default=dict, help_text="accuracy/precision/recall/f1_score at training time")
    is_active = models.BooleanField(default=False, help_text="Only one model version should be active at a time.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trained_at"]

    def __str__(self):
        return f"{self.version_name} ({self.algorithm}){' [active]' if self.is_active else ''}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            # Enforce "only one active model" at the DB level rather than
            # relying on whoever calls save() to remember to deactivate
            # the others first.
            ModelVersion.objects.exclude(pk=self.pk).update(is_active=False)


class Prediction(models.Model):
    """One prediction run for one machine, using one specific ModelVersion."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="predictions")
    model_version = models.ForeignKey(ModelVersion, on_delete=models.PROTECT, related_name="predictions")

    failure_probability = models.FloatField(help_text="Model's predicted probability (0-1) that maintenance is needed soon")
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES)

    # Kept for schema compatibility with the Prompt 1 architecture's
    # `predicted_rul_days` column. The current model is a binary classifier
    # (probability of "needs maintenance soon"), not a regressor, so this
    # is left null for now — populating it would require a separate
    # regression model trained on time-to-failure, which is a natural
    # future extension once real historical failure data is available.
    predicted_rul_days = models.IntegerField(null=True, blank=True)

    input_snapshot = models.JSONField(
        default=dict,
        help_text="The exact feature values used for this prediction, kept for auditability/debugging.",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_predictions"
    )
    predicted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-predicted_at"]
        indexes = [
            models.Index(fields=["machine", "-predicted_at"]),
            models.Index(fields=["risk_level"]),
        ]

    def __str__(self):
        return f"{self.machine.machine_code} — {self.get_risk_level_display()} ({self.failure_probability:.2f}) @ {self.predicted_at:%Y-%m-%d %H:%M}"

    @property
    def risk_badge_class(self):
        return RISK_BADGE_CLASS.get(self.risk_level, "bg-secondary")
