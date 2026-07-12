from django.contrib import admin

from .models import Comment, MaintenanceRequest, Notification, StatusHistory


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("created_at",)


class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    readonly_fields = ("changed_at",)


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "machine", "priority", "status", "assigned_engineer", "scheduled_date", "created_at")
    list_filter = ("status", "priority", "machine__department")
    search_fields = ("title", "machine__name", "machine__machine_code")
    date_hierarchy = "created_at"
    inlines = [StatusHistoryInline, CommentInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "message")
