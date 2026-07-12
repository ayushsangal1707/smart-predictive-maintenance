from django.urls import path

from . import views

app_name = "predictions"

urlpatterns = [
    path("run/", views.run_prediction, name="run"),
    path("", views.prediction_list, name="list"),
    path("<int:pk>/", views.prediction_detail, name="detail"),
    path("machine/<int:machine_id>/", views.machine_prediction_history, name="machine_history"),

    # JSON / AJAX API
    path("api/run/<int:machine_id>/", views.api_run_prediction, name="api_run"),
    path("api/trend/<int:machine_id>/", views.api_prediction_trend, name="api_trend"),
]
