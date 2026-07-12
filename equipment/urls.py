from django.urls import path

from . import views

app_name = "equipment"

urlpatterns = [
    path("", views.machine_list, name="list"),
    path("add/", views.machine_create, name="create"),
    path("<int:pk>/", views.machine_detail, name="detail"),
    path("<int:pk>/edit/", views.machine_update, name="update"),
    path("<int:pk>/delete/", views.machine_delete, name="delete"),
]
