from django.urls import path

from . import views

app_name = "sensors"

urlpatterns = [
    # Sensor definitions (setup)
    path("definitions/", views.definition_list, name="definition_list"),
    path("definitions/add/", views.definition_create, name="definition_create"),
    path("definitions/<int:pk>/edit/", views.definition_update, name="definition_update"),
    path("definitions/<int:pk>/delete/", views.definition_delete, name="definition_delete"),

    # Readings
    path("manual-entry/", views.manual_entry, name="manual_entry"),
    path("upload/", views.upload_readings, name="upload"),
    path("history/", views.reading_history, name="history"),

    # AJAX / JSON
    path("api/machines/<int:machine_id>/sensors/", views.api_sensors_for_machine, name="api_sensors_for_machine"),
]
