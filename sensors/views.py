import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from accounts.decorators import role_required
from core.constants import ROLE_ADMIN, ROLE_ENGINEER
from equipment.models import Machine

from .forms import ManualReadingForm, ReadingUploadForm, SensorDefinitionForm
from .models import SensorDefinition, SensorReading
from .utils import UploadParseError, process_reading_upload

PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Sensor Definitions (setup/config, not raw readings)
# ---------------------------------------------------------------------------

@login_required
def definition_list(request):
    definitions = SensorDefinition.objects.select_related("machine").all()
    machine_id = request.GET.get("machine", "")
    if machine_id:
        definitions = definitions.filter(machine_id=machine_id)

    return render(request, "sensors/definition_list.html", {
        "definitions": definitions,
        "machines": Machine.objects.all(),
        "selected_machine": machine_id,
    })


@role_required(ROLE_ADMIN, ROLE_ENGINEER)
def definition_create(request):
    if request.method == "POST":
        form = SensorDefinitionForm(request.POST)
        if form.is_valid():
            definition = form.save()
            messages.success(request, f"Sensor '{definition.sensor_name}' added to {definition.machine.name}.")
            return redirect("sensors:definition_list")
    else:
        form = SensorDefinitionForm(initial={"machine": request.GET.get("machine")})

    return render(request, "sensors/definition_form.html", {"form": form, "is_edit": False})


@role_required(ROLE_ADMIN, ROLE_ENGINEER)
def definition_update(request, pk):
    definition = get_object_or_404(SensorDefinition, pk=pk)
    if request.method == "POST":
        form = SensorDefinitionForm(request.POST, instance=definition)
        if form.is_valid():
            form.save()
            messages.success(request, "Sensor definition updated.")
            return redirect("sensors:definition_list")
    else:
        form = SensorDefinitionForm(instance=definition)

    return render(request, "sensors/definition_form.html", {"form": form, "is_edit": True, "definition": definition})


@role_required(ROLE_ADMIN, ROLE_ENGINEER)
def definition_delete(request, pk):
    definition = get_object_or_404(SensorDefinition, pk=pk)
    if request.method == "POST":
        name = definition.sensor_name
        definition.delete()
        messages.success(request, f"Sensor '{name}' deleted.")
        return redirect("sensors:definition_list")
    return render(request, "sensors/definition_confirm_delete.html", {"definition": definition})


# ---------------------------------------------------------------------------
# Manual Entry
# ---------------------------------------------------------------------------

@login_required
def manual_entry(request):
    if request.method == "POST":
        form = ManualReadingForm(request.POST)
        if form.is_valid():
            reading = form.save(commit=False)
            reading.source = "MANUAL"
            reading.created_by = request.user
            reading.save()
            messages.success(
                request,
                f"Reading recorded: {reading.sensor.sensor_name} = {reading.value} {reading.sensor.get_unit_display()}",
            )
            return redirect("sensors:manual_entry")
    else:
        form = ManualReadingForm()

    return render(request, "sensors/manual_entry.html", {"form": form})


# ---------------------------------------------------------------------------
# CSV / Excel Upload
# ---------------------------------------------------------------------------

@login_required
def upload_readings(request):
    result = None

    if request.method == "POST":
        form = ReadingUploadForm(request.POST, request.FILES)
        if form.is_valid():
            machine = form.cleaned_data["machine"]
            uploaded_file = form.cleaned_data["file"]
            try:
                result = process_reading_upload(
                    uploaded_file=uploaded_file,
                    machine=machine,
                    user=request.user,
                )
                if result["created"]:
                    messages.success(request, f"Imported {result['created']} reading(s) successfully.")
                if result["skipped"]:
                    messages.warning(request, f"{result['skipped']} row(s) were skipped due to errors — see details below.")
                if not result["created"] and not result["skipped"]:
                    messages.info(request, "No rows were found to import.")
            except UploadParseError as exc:
                messages.error(request, str(exc))
    else:
        form = ReadingUploadForm()

    return render(request, "sensors/upload.html", {"form": form, "result": result})


# ---------------------------------------------------------------------------
# History (list + filters + chart)
# ---------------------------------------------------------------------------

@login_required
def reading_history(request):
    readings = SensorReading.objects.select_related("sensor", "sensor__machine")

    machine_id = request.GET.get("machine", "")
    sensor_id = request.GET.get("sensor", "")
    source = request.GET.get("source", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    anomalies_only = request.GET.get("anomalies_only", "")

    if machine_id:
        readings = readings.filter(sensor__machine_id=machine_id)
    if sensor_id:
        readings = readings.filter(sensor_id=sensor_id)
    if source:
        readings = readings.filter(source=source)
    if date_from:
        parsed = parse_date(date_from)
        if parsed:
            readings = readings.filter(recorded_at__date__gte=parsed)
    if date_to:
        parsed = parse_date(date_to)
        if parsed:
            readings = readings.filter(recorded_at__date__lte=parsed)
    if anomalies_only == "1":
        readings = readings.out_of_range()

    paginator = Paginator(readings, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    querydict = request.GET.copy()
    querydict.pop("page", None)
    querystring = querydict.urlencode()

    sensors_qs = SensorDefinition.objects.select_related("machine")
    if machine_id:
        sensors_qs = sensors_qs.filter(machine_id=machine_id)

    # Chart data: last 100 readings matching the current filters, oldest
    # first, so the line chart reads left-to-right chronologically.
    chart_qs = list(readings.order_by("-recorded_at")[:100])[::-1]
    chart_data = {
        "labels": [r.recorded_at.strftime("%Y-%m-%d %H:%M") for r in chart_qs],
        "values": [r.value for r in chart_qs],
        "sensor_name": chart_qs[0].sensor.sensor_name if chart_qs else "",
        "unit": chart_qs[0].sensor.get_unit_display() if chart_qs else "",
        "normal_min": chart_qs[0].sensor.normal_min if chart_qs else None,
        "normal_max": chart_qs[0].sensor.normal_max if chart_qs else None,
    }

    context = {
        "page_obj": page_obj,
        "machines": Machine.objects.all(),
        "sensors": sensors_qs,
        "source_choices": SensorReading._meta.get_field("source").choices,
        "machine_id": machine_id,
        "sensor_id": sensor_id,
        "source": source,
        "date_from": date_from,
        "date_to": date_to,
        "anomalies_only": anomalies_only,
        "querystring": querystring,
        "total_count": paginator.count,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "sensors/history.html", context)


# ---------------------------------------------------------------------------
# Lightweight JSON/AJAX endpoints
# ---------------------------------------------------------------------------

@login_required
def api_sensors_for_machine(request, machine_id):
    """Used by manual_entry.html to populate the sensor dropdown via AJAX
    once a machine is selected, without a full page reload."""
    sensors = SensorDefinition.objects.filter(machine_id=machine_id, is_active=True).values(
        "id", "sensor_name", "unit"
    )
    return JsonResponse({"sensors": list(sensors)})
