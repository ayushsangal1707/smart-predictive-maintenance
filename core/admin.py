from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "model_name", "object_repr", "ip_address")
    list_filter = ("action", "model_name")
    search_fields = ("user__username", "object_repr", "description")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        # Audit entries are only ever created by the application itself.
        return False
