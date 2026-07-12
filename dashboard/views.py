from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
import json

from core.constants import DEPARTMENT_CHOICES, MACHINE_STATUS_CHOICES
from equipment.models import Machine
from predictions.models import RISK_CHOICES, Prediction

from .services import (
    build_machine_sensor_charts,
    build_maintenance_stats,
    build_monthly_report,
    build_risk_distribution,
    get_latest_prediction_map,
)

MACHINE_GRID_PAGE_SIZE = 12
RECENT_ALERTS_LIMIT = 8


@login_required
def home(request):
    # --- Search / filters for the machine health grid ---------------------
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    department = request.GET.get("department", "")
    risk_filter = request.GET.get("risk_level", "")

    machines = Machine.objects.all()
    if query:
        machines = machines.filter(
            name__icontains=query
        ) | machines.filter(machine_code__icontains=query)
    if status:
        machines = machines.filter(status=status)
    if department:
        machines = machines.filter(department=department)

    # latest_predictions is a plant-wide aggregate — identical for every
    # user viewing the dashboard at a given moment — so it's cached briefly
    # rather than recomputed on every request. 60s keeps the dashboard
    # feeling live while avoiding redundant work under concurrent traffic
    # (several people on the dashboard at once, or the 30s notification-
    # bell poll happening in the background).
    latest_predictions = cache.get_or_set("dashboard:latest_predictions", get_latest_prediction_map, timeout=60)

    if risk_filter:
        machines = [m for m in machines if latest_predictions.get(m.id) and latest_predictions[m.id].risk_level == risk_filter]
    else:
        machines = list(machines)

    paginator = Paginator(machines, MACHINE_GRID_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Attach each paginated machine's latest prediction for the template
    # (avoids a template-level DB lookup per row).
    for machine in page_obj:
        machine.latest_prediction = latest_predictions.get(machine.id)

    querydict = request.GET.copy()
    querydict.pop("page", None)
    querystring = querydict.urlencode()

    # --- Top stat cards -----------------------------------------------------
    total_machines = Machine.objects.count()
    active_machines = Machine.objects.filter(status="ACTIVE").count()
    risk_counts = build_risk_distribution(latest_predictions)
    machines_with_predictions = len(latest_predictions)
    avg_failure_probability = (
        sum(p.failure_probability for p in latest_predictions.values()) / machines_with_predictions
        if machines_with_predictions else 0
    )

    # --- Recent alerts (derived from High/Critical predictions) ------------
    # NOTE: there's no dedicated Alert model yet — that's built in the
    # Maintenance module (a later prompt). Until then, "recent alerts" are
    # simply the most recent High/Critical-risk predictions across all
    # machines, which is exactly what a dedicated alert would be generated
    # from anyway. Swapping this for a real Alert queryset later is a
    # one-line change once that model exists.
    recent_alerts = (
        Prediction.objects.filter(risk_level__in=["HIGH", "CRITICAL"])
        .select_related("machine")
        .order_by("-predicted_at")[:RECENT_ALERTS_LIMIT]
    )

    # --- Monthly report chart ------------------------------------------------
    monthly_report = cache.get_or_set("dashboard:monthly_report", build_monthly_report, timeout=60)

    # --- Maintenance module dashboard cards (Prompt 8) ----------------------
    maintenance_stats = build_maintenance_stats()

    # --- Machine sensor graphs (Temperature / Pressure / Vibration) ---------
    selected_machine_id = request.GET.get("machine")
    selected_machine = None
    if selected_machine_id:
        selected_machine = Machine.objects.filter(pk=selected_machine_id).first()
    if selected_machine is None:
        # Default to whichever machine has the most recent sensor reading,
        # so the dashboard opens showing genuinely active/interesting data.
        selected_machine = Machine.objects.order_by("-sensor_definitions__readings__recorded_at").first()

    sensor_charts = build_machine_sensor_charts(selected_machine) if selected_machine else {}

    context = {
        "total_machines": total_machines,
        "active_machines": active_machines,
        "risk_counts": risk_counts,
        "avg_failure_probability": avg_failure_probability,
        "recent_alerts": recent_alerts,
        "monthly_report": monthly_report,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "department": department,
        "risk_filter": risk_filter,
        "status_choices": MACHINE_STATUS_CHOICES,
        "department_choices": DEPARTMENT_CHOICES,
        "risk_choices": RISK_CHOICES,
        "querystring": querystring,
        "all_machines": Machine.objects.all().order_by("name"),
        "selected_machine": selected_machine,
        "sensor_charts": sensor_charts,
        "risk_counts_json": json.dumps(risk_counts),
        "monthly_report_json": json.dumps(monthly_report),
        "sensor_charts_json": json.dumps(sensor_charts),
        "maintenance_stats": maintenance_stats,
    }
    return render(request, "dashboard/home.html", context)


@login_required
def api_machine_dashboard_data(request, machine_id):
    """
    AJAX endpoint used by the machine-picker dropdown on the dashboard: lets
    the Temperature/Pressure/Vibration graphs (and the risk summary) update
    for a newly selected machine without a full page reload.
    """
    machine = get_object_or_404(Machine, pk=machine_id)
    latest_predictions = get_latest_prediction_map()
    latest = latest_predictions.get(machine.id)

    return JsonResponse({
        "machine": {"id": machine.id, "name": machine.name, "code": machine.machine_code},
        "latest_prediction": {
            "risk_level": latest.risk_level,
            "risk_level_display": latest.get_risk_level_display(),
            "failure_probability": latest.failure_probability,
            "predicted_at": latest.predicted_at.isoformat(),
        } if latest else None,
        "sensor_charts": build_machine_sensor_charts(machine),
    })
