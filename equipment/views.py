from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from core.audit import log_activity
from core.constants import DEPARTMENT_CHOICES, MACHINE_STATUS_CHOICES, MACHINE_TYPE_CHOICES, ROLE_ADMIN, ROLE_ENGINEER

from .forms import MachineForm
from .models import Machine

PAGE_SIZE = 10


@login_required
def machine_list(request):
    machines = Machine.objects.all()

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    department = request.GET.get("department", "")
    machine_type = request.GET.get("machine_type", "")

    if query:
        machines = machines.filter(
            Q(machine_code__icontains=query)
            | Q(name__icontains=query)
            | Q(manufacturer__icontains=query)
            | Q(location__icontains=query)
        )
    if status:
        machines = machines.filter(status=status)
    if department:
        machines = machines.filter(department=department)
    if machine_type:
        machines = machines.filter(machine_type=machine_type)

    paginator = Paginator(machines, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Preserve current filters/search when building pagination links, so
    # clicking "next page" doesn't silently reset the search/filter state.
    querydict = request.GET.copy()
    querydict.pop("page", None)
    querystring = querydict.urlencode()

    context = {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "department": department,
        "machine_type": machine_type,
        "status_choices": MACHINE_STATUS_CHOICES,
        "department_choices": DEPARTMENT_CHOICES,
        "machine_type_choices": MACHINE_TYPE_CHOICES,
        "querystring": querystring,
        "total_count": paginator.count,
    }
    return render(request, "equipment/list.html", context)


@login_required
def machine_detail(request, pk):
    machine = get_object_or_404(Machine, pk=pk)

    # Lazy import: avoids equipment/views.py depending on predictions at
    # module-load time (predictions.models imports equipment.models, so
    # importing the other way around at the top of this file would risk
    # a circular import during Django's app-loading sequence).
    from predictions.models import Prediction
    latest_prediction = Prediction.objects.filter(machine=machine).select_related("model_version").first()

    return render(request, "equipment/detail.html", {"machine": machine, "latest_prediction": latest_prediction})


@role_required(ROLE_ADMIN, ROLE_ENGINEER)
def machine_create(request):
    if request.method == "POST":
        form = MachineForm(request.POST)
        if form.is_valid():
            machine = form.save(commit=False)
            machine.created_by = request.user
            machine.save()
            log_activity(request.user, "CREATE", machine, request=request)
            messages.success(request, f"Machine '{machine.name}' added successfully.")
            return redirect("equipment:detail", pk=machine.pk)
    else:
        form = MachineForm()

    return render(request, "equipment/form.html", {"form": form, "is_edit": False})


@role_required(ROLE_ADMIN, ROLE_ENGINEER)
def machine_update(request, pk):
    machine = get_object_or_404(Machine, pk=pk)

    if request.method == "POST":
        form = MachineForm(request.POST, instance=machine)
        if form.is_valid():
            form.save()
            log_activity(request.user, "UPDATE", machine, request=request)
            messages.success(request, f"Machine '{machine.name}' updated successfully.")
            return redirect("equipment:detail", pk=machine.pk)
    else:
        form = MachineForm(instance=machine)

    return render(request, "equipment/form.html", {"form": form, "is_edit": True, "machine": machine})


@role_required(ROLE_ADMIN, ROLE_ENGINEER)
def machine_delete(request, pk):
    machine = get_object_or_404(Machine, pk=pk)

    if request.method == "POST":
        name = machine.name
        log_activity(request.user, "DELETE", machine, description=f"Deleted machine '{name}'", request=request)
        machine.delete()
        messages.success(request, f"Machine '{name}' deleted.")
        return redirect("equipment:list")

    return render(request, "equipment/confirm_delete.html", {"machine": machine})
