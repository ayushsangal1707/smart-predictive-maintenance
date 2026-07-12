from django.contrib import admin

from .models import SensorDefinition, SensorReading


@admin.register(SensorDefinition)
class SensorDefinitionAdmin(admin.ModelAdmin):
    list_display = ("sensor_name", "machine", "unit", "normal_min", "normal_max", "is_active")
    list_filter = ("unit", "is_active", "machine__department")
    search_fields = ("sensor_name", "machine__name", "machine__machine_code")


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ("sensor", "value", "recorded_at", "source", "created_by", "is_out_of_range")
    list_filter = ("source", "sensor__machine")
    search_fields = ("sensor__sensor_name", "sensor__machine__name", "sensor__machine__machine_code")
    date_hierarchy = "recorded_at"
    readonly_fields = ("created_at",)

    @admin.display(boolean=True, description="Out of range")
    def is_out_of_range(self, obj):
        return obj.is_out_of_range
