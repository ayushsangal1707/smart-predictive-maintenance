from django.contrib import admin

from .models import Machine


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        "machine_code",
        "name",
        "machine_type",
        "department",
        "status",
        "installation_date",
        "created_by",
    )
    list_filter = ("status", "department", "machine_type")
    search_fields = ("machine_code", "name", "manufacturer", "location")
    date_hierarchy = "installation_date"
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    fieldsets = (
        ("Identification", {"fields": ("machine_code", "name", "machine_type", "department")}),
        ("Details", {"fields": ("location", "manufacturer", "installation_date", "status", "description")}),
        ("Audit", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
