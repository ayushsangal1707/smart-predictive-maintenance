from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.request_list, name="list"),
    path("add/", views.request_create, name="create"),
    path("<int:pk>/", views.request_detail, name="detail"),
    path("<int:pk>/assign/", views.request_assign, name="assign"),
    path("<int:pk>/schedule/", views.request_schedule, name="schedule"),
    path("<int:pk>/status/", views.request_update_status, name="update_status"),
    path("<int:pk>/comment/", views.request_add_comment, name="add_comment"),

    # Notifications
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:pk>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/read-all/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("api/notifications/unread-count/", views.api_unread_notification_count, name="api_unread_count"),
    path("api/notifications/recent/", views.api_recent_notifications, name="api_recent_notifications"),
]
