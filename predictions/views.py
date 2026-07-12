import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from equipment.models import Machine
from core.audit import log_activity

from .forms import RunPredictionForm
from .ml.predict import PredictionError, predict_for_machine
from .models import RISK_CHOICES, Prediction

PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Run a new prediction (the "Upload Data -> Prediction" step of the workflow;
# "Upload Data" itself already happened via the Sensor Data module in
# Prompt 4 — this view is where that stored data gets turned into a result)
# ---------------------------------------------------------------------------

@login_required
def run_prediction(request):
    if request.method == "POST":
        form = RunPredictionForm(request.POST)
        if form.is_valid():
            machine = form.cleaned_data["machine"]
            try:
                prediction = predict_for_machine(machine, user=request.user)
                log_activity(request.user, "PREDICT", prediction, request=request)
                messages.success(
                    request,
                    f"Prediction complete for {machine.name}: "
                    f"{prediction.get_risk_level_display()} risk "
                    f"({prediction.failure_probability:.0%} probability).",
                )
                return redirect("predictions:detail", pk=prediction.pk)
            except PredictionError as exc:
                messages.error(request, str(exc))
    else:
        initial = {}
        machine_id = request.GET.get("machine")
        if machine_id:
            initial["machine"] = machine_id
        form = RunPredictionForm(initial=initial)

    return render(request, "predictions/run_form.html", {"form": form})


# ---------------------------------------------------------------------------
# Store Result -> browse results
# ---------------------------------------------------------------------------

@login_required
def prediction_detail(request, pk):
    prediction = get_object_or_404(Prediction, pk=pk)
    return render(request, "predictions/detail.html", {"prediction": prediction})


@login_required
def prediction_list(request):
    predictions = Prediction.objects.select_related("machine", "model_version")

    machine_id = request.GET.get("machine", "")
    risk_level = request.GET.get("risk_level", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    if machine_id:
        predictions = predictions.filter(machine_id=machine_id)
    if risk_level:
        predictions = predictions.filter(risk_level=risk_level)
    if date_from:
        parsed = parse_date(date_from)
        if parsed:
            predictions = predictions.filter(predicted_at__date__gte=parsed)
    if date_to:
        parsed = parse_date(date_to)
        if parsed:
            predictions = predictions.filter(predicted_at__date__lte=parsed)

    paginator = Paginator(predictions, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    querydict = request.GET.copy()
    querydict.pop("page", None)
    querystring = querydict.urlencode()

    return render(request, "predictions/list.html", {
        "page_obj": page_obj,
        "machines": Machine.objects.all(),
        "risk_choices": RISK_CHOICES,
        "machine_id": machine_id,
        "risk_level": risk_level,
        "date_from": date_from,
        "date_to": date_to,
        "querystring": querystring,
        "total_count": paginator.count,
    })


@login_required
def machine_prediction_history(request, machine_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    predictions = Prediction.objects.filter(machine=machine).select_related("model_version")

    paginator = Paginator(predictions, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    chart_qs = list(predictions.order_by("-predicted_at")[:50])[::-1]
    chart_data = {
        "labels": [p.predicted_at.strftime("%Y-%m-%d %H:%M") for p in chart_qs],
        "values": [p.failure_probability for p in chart_qs],
    }

    latest = predictions.first()

    return render(request, "predictions/machine_history.html", {
        "machine": machine,
        "page_obj": page_obj,
        "latest": latest,
        "chart_data_json": json.dumps(chart_data),
    })


# ---------------------------------------------------------------------------
# JSON / AJAX API (per the Prompt 1 API design)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def api_run_prediction(request, machine_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    try:
        prediction = predict_for_machine(machine, user=request.user)
    except PredictionError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse({
        "success": True,
        "prediction_id": prediction.pk,
        "machine": machine.name,
        "failure_probability": prediction.failure_probability,
        "risk_level": prediction.risk_level,
        "risk_level_display": prediction.get_risk_level_display(),
        "predicted_at": prediction.predicted_at.isoformat(),
    })


@login_required
def api_prediction_trend(request, machine_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    days = int(request.GET.get("days", 30))
    cutoff = timezone.now() - timedelta(days=days)

    predictions = (
        Prediction.objects.filter(machine=machine, predicted_at__gte=cutoff)
        .order_by("-predicted_at")[:200]
    )
    chart_qs = list(predictions)[::-1]

    return JsonResponse({
        "machine": machine.name,
        "labels": [p.predicted_at.strftime("%Y-%m-%d %H:%M") for p in chart_qs],
        "values": [p.failure_probability for p in chart_qs],
        "risk_levels": [p.risk_level for p in chart_qs],
    })
