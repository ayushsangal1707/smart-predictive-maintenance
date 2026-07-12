from django.contrib import admin

from .models import ModelVersion, Prediction


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ("version_name", "algorithm", "trained_at", "is_active")
    list_filter = ("algorithm", "is_active")
    readonly_fields = ("created_at",)
    ordering = ("-trained_at",)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("machine", "risk_level", "failure_probability", "model_version", "requested_by", "predicted_at")
    list_filter = ("risk_level", "model_version")
    search_fields = ("machine__name", "machine__machine_code")
    date_hierarchy = "predicted_at"
    readonly_fields = ("predicted_at", "input_snapshot")
