"""
dashboard/services.py
-----------------------
Shared data-building helpers used by both the server-rendered dashboard
view and its AJAX JSON endpoint (dashboard/views.py), so the two never
drift out of sync with each other.
"""

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from predictions.ml.predict import SENSOR_KEYWORD_MAP
from predictions.models import Prediction
from sensors.models import SensorDefinition, SensorReading

# Which of the model's sensor keys the dashboard charts (Temperature /
# Pressure / Vibration graphs, per the prompt) actually display. RPM isn't
# one of the requested dashboard graphs, so it's intentionally left out
# here even though the ML module (Prompt 5/6) also tracks it.
DASHBOARD_CHART_SENSORS = ["temperature", "pressure", "vibration"]

CHART_POINTS = 30  # how many most-recent readings to chart per sensor


def _find_sensor_definition(machine, model_key):
    """Reuses the same keyword-matching approach as predictions/ml/predict.py
    (e.g. 'temperature' matches a SensorDefinition named 'Bearing Temperature')
    so the dashboard charts the same sensor the prediction engine reads from."""
    for definition in SensorDefinition.objects.filter(machine=machine, is_active=True):
        name = definition.sensor_name.strip().lower()
        for keyword, key in SENSOR_KEYWORD_MAP.items():
            if key == model_key and keyword in name:
                return definition
    return None


def build_machine_sensor_charts(machine):
    """
    Returns chart-ready data for the Temperature / Pressure / Vibration
    graphs for one machine, e.g.:
        {
            "temperature": {"labels": [...], "values": [...], "unit": "°C",
                             "normal_min": 20, "normal_max": 80, "sensor_name": "..."},
            "pressure": {...} or None if no matching sensor exists,
            "vibration": {...} or None,
        }
    A None value means the machine has no sensor matching that keyword —
    the template/JS shows "No data" for that graph instead of erroring.
    """
    charts = {}
    for model_key in DASHBOARD_CHART_SENSORS:
        definition = _find_sensor_definition(machine, model_key)
        if definition is None:
            charts[model_key] = None
            continue

        readings = list(
            SensorReading.objects.filter(sensor=definition).order_by("-recorded_at")[:CHART_POINTS]
        )[::-1]

        charts[model_key] = {
            "sensor_name": definition.sensor_name,
            "unit": definition.get_unit_display(),
            "normal_min": definition.normal_min,
            "normal_max": definition.normal_max,
            "labels": [r.recorded_at.strftime("%Y-%m-%d %H:%M") for r in readings],
            "values": [r.value for r in readings],
        }
    return charts


def get_latest_prediction_map():
    """
    Returns {machine_id: latest Prediction} for every machine that has at
    least one prediction, in a single query rather than one query per
    machine (which would be an N+1 problem on the machine health grid).
    """
    latest_per_machine = {}
    predictions = Prediction.objects.select_related("machine").order_by("machine_id", "-predicted_at")
    seen_machines = set()
    for p in predictions:
        if p.machine_id not in seen_machines:
            latest_per_machine[p.machine_id] = p
            seen_machines.add(p.machine_id)
    return latest_per_machine


def build_risk_distribution(latest_predictions):
    """Counts how many machines currently sit in each risk band, based on
    each machine's most recent prediction only (not all historical ones)."""
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for prediction in latest_predictions.values():
        counts[prediction.risk_level] = counts.get(prediction.risk_level, 0) + 1
    return counts


def build_monthly_report(months=6):
    """
    Aggregates prediction runs per month for the last `months` months:
    total predictions run, and how many came back High/Critical risk.
    Powers the "Monthly Reports" bar chart on the dashboard.
    """
    now = timezone.now()
    # Build the list of the last `months` (year, month) buckets, oldest first,
    # so the chart reads left-to-right chronologically even for months with
    # zero predictions (which a simple .annotate(month=...) query would
    # otherwise silently skip).
    buckets = []
    year, month = now.year, now.month
    for _ in range(months):
        buckets.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    buckets.reverse()

    cutoff = now - timedelta(days=31 * months)
    predictions = Prediction.objects.filter(predicted_at__gte=cutoff)

    totals = defaultdict(int)
    critical_counts = defaultdict(int)
    for p in predictions:
        key = (p.predicted_at.year, p.predicted_at.month)
        totals[key] += 1
        if p.risk_level in ("HIGH", "CRITICAL"):
            critical_counts[key] += 1

    labels = [f"{y}-{m:02d}" for y, m in buckets]
    total_values = [totals.get(b, 0) for b in buckets]
    critical_values = [critical_counts.get(b, 0) for b in buckets]

    return {"labels": labels, "total": total_values, "high_critical": critical_values}


def build_maintenance_stats():
    """
    Dashboard-card summary of the Maintenance module (Prompt 8): open
    requests, how many are overdue, and how many were completed in the
    last 30 days. Imported lazily inside the function (not at module
    top-level) to avoid a hard import-time dependency between the
    dashboard and maintenance apps — dashboard/services.py is otherwise
    only aware of equipment/sensors/predictions.
    """
    from maintenance.models import MaintenanceRequest, OPEN_STATUSES, STATUS_COMPLETED

    now = timezone.now()
    open_qs = MaintenanceRequest.objects.filter(status__in=OPEN_STATUSES)

    return {
        "open_count": open_qs.count(),
        "overdue_count": open_qs.filter(scheduled_date__lt=now).count(),
        "completed_last_30_days": MaintenanceRequest.objects.filter(
            status=STATUS_COMPLETED, completed_at__gte=now - timedelta(days=30)
        ).count(),
    }
