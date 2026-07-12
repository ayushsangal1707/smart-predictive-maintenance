from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import render

from core.audit import log_activity
from equipment.models import Machine
from maintenance.models import MaintenanceRequest, OPEN_STATUSES
from predictions.models import Prediction, RISK_CHOICES

from .generators import (
    export_machines_csv,
    export_machines_excel,
    export_maintenance_csv,
    export_maintenance_excel,
    export_predictions_csv,
    export_predictions_excel,
    generate_summary_pdf,
)


@login_required
def reports_home(request):
    return render(request, "reports/home.html", {"machines": Machine.objects.all()})


@login_required
def export_machines(request, file_format):
    queryset = Machine.objects.all()
    machine_id = request.GET.get("machine")
    if machine_id:
        queryset = queryset.filter(pk=machine_id)

    if file_format == "csv":
        response = export_machines_csv(queryset)
    elif file_format == "excel":
        response = export_machines_excel(queryset)
    else:
        return HttpResponseBadRequest("Unknown export format.")

    log_activity(request.user, "EXPORT", description=f"Exported machines ({file_format})", request=request)
    return response


@login_required
def export_predictions(request, file_format):
    queryset = Prediction.objects.select_related("machine", "model_version").all()
    machine_id = request.GET.get("machine")
    if machine_id:
        queryset = queryset.filter(machine_id=machine_id)

    if file_format == "csv":
        response = export_predictions_csv(queryset)
    elif file_format == "excel":
        response = export_predictions_excel(queryset)
    else:
        return HttpResponseBadRequest("Unknown export format.")

    log_activity(request.user, "EXPORT", description=f"Exported predictions ({file_format})", request=request)
    return response


@login_required
def export_maintenance(request, file_format):
    queryset = MaintenanceRequest.objects.select_related("machine", "assigned_engineer", "requested_by").all()
    machine_id = request.GET.get("machine")
    if machine_id:
        queryset = queryset.filter(machine_id=machine_id)

    if file_format == "csv":
        response = export_maintenance_csv(queryset)
    elif file_format == "excel":
        response = export_maintenance_excel(queryset)
    else:
        return HttpResponseBadRequest("Unknown export format.")

    log_activity(request.user, "EXPORT", description=f"Exported maintenance requests ({file_format})", request=request)
    return response


@login_required
def export_summary_pdf(request):
    total_machines = Machine.objects.count()
    active_machines = Machine.objects.filter(status="ACTIVE").count()
    under_maintenance_machines = Machine.objects.filter(status="UNDER_MAINTENANCE").count()

    # Latest prediction per machine, grouped by risk level (same approach as
    # dashboard/services.py's build_risk_distribution, kept independent here
    # so the reports app doesn't need to import from the dashboard app).
    latest_by_machine = {}
    for p in Prediction.objects.select_related("machine").order_by("machine_id", "-predicted_at"):
        if p.machine_id not in latest_by_machine:
            latest_by_machine[p.machine_id] = p
    risk_counts = {label: 0 for _, label in RISK_CHOICES}
    risk_key_to_label = dict(RISK_CHOICES)
    for p in latest_by_machine.values():
        risk_counts[risk_key_to_label.get(p.risk_level, p.risk_level)] += 1

    open_requests = list(
        MaintenanceRequest.objects.filter(status__in=OPEN_STATUSES)
        .select_related("machine", "assigned_engineer")
        .order_by("-priority", "-created_at")[:15]
    )

    stats = {
        "total_machines": total_machines,
        "active_machines": active_machines,
        "under_maintenance_machines": under_maintenance_machines,
        "risk_counts": risk_counts,
        "open_requests": open_requests,
    }

    response = generate_summary_pdf(stats)
    log_activity(request.user, "EXPORT", description="Exported plant summary PDF report", request=request)
    return response
