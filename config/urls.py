from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("equipment/", include("equipment.urls")),
    path("sensors/", include("sensors.urls")),
    path("predictions/", include("predictions.urls")),
    path("maintenance/", include("maintenance.urls")),
    path("reports/", include("reports.urls")),
    path("system/", include("core.urls")),
    path("", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
