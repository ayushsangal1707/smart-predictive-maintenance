from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_home, name="home"),
    path("machines/<str:file_format>/", views.export_machines, name="export_machines"),
    path("predictions/<str:file_format>/", views.export_predictions, name="export_predictions"),
    path("maintenance/<str:file_format>/", views.export_maintenance, name="export_maintenance"),
    path("summary/pdf/", views.export_summary_pdf, name="export_summary_pdf"),
]
