from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/machine/<int:machine_id>/", views.api_machine_dashboard_data, name="api_machine_data"),
]
