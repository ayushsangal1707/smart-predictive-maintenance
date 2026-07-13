from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.constants import ROLE_ADMIN, ROLE_MANAGER
from core.audit import log_activity
from equipment.models import Machine
from predictions.models import Prediction

from .forms import AssignEngineerForm, CommentForm, MaintenanceRequestForm, ScheduleForm, StatusUpdateForm
from .models import MaintenanceRequest, Notification, PRIORITY_CHOICES, STATUS_CHOICES
from .services import add_comment, assign_engineer, build_timeline, change_status, schedule_request

PAGE_SIZE = 15


def _is_admin_or_manager(user):
    """True only for Admin/Manager roles — the single source of truth for
    'has elevated maintenance privileges', used by every check below."""
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role in (ROLE_ADMIN, ROLE_MANAGER))


def _can_assign(user):
    """Only Admin/Manager may assign an engineer to a request."""
    return _is_admin_or_manager(user)


def _can_schedule(user):
    """
    Only Admin/Manager may schedule maintenance. An assigned Engineer does
    the work but does NOT control scheduling — this is intentionally
    stricter than _can_update_status below.
    """
    return _is_admin_or_manager(user)


def _can_update_status(user, request_obj):
    """
    Admin/Manager can update ANY request's status. An Engineer may update
    status ONLY on a request they are specifically assigned to — never on
    other Engineers' requests, and never to assign/reassign someone else.
    """
    if _is_admin_or_manager(user):
        return True
    return request_obj.assigned_engineer_id == user.id

# ---------------------------------------------------------------------------
# Maintenance Request: list, create, detail
# ---------------------------------------------------------------------------

@login_required
def request_list(request):
    requests_qs = MaintenanceRequest.objects.select_related("machine", "assigned_engineer", "requested_by")

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    machine_id = request.GET.get("machine", "")
    my_requests = request.GET.get("my", "")

    if query:
        requests_qs = requests_qs.filter(title__icontains=query)
    if status:
        requests_qs = requests_qs.filter(status=status)
    if priority:
        requests_qs = requests_qs.filter(priority=priority)
    if machine_id:
        requests_qs = requests_qs.filter(machine_id=machine_id)
    if my_requests == "1":
        requests_qs = requests_qs.filter(assigned_engineer=request.user)

    paginator = Paginator(requests_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    querydict = request.GET.copy()
    querydict.pop("page", None)
    querystring = querydict.urlencode()

    return render(request, "maintenance/request_list.html", {
        "page_obj": page_obj,
        "machines": Machine.objects.all(),
        "status_choices": STATUS_CHOICES,
        "priority_choices": PRIORITY_CHOICES,
        "query": query,
        "status": status,
        "priority": priority,
        "machine_id": machine_id,
        "my_requests": my_requests,
        "querystring": querystring,
        "total_count": paginator.count,
    })


@login_required
def request_create(request):
    initial = {}
    machine_id = request.GET.get("machine")
    if machine_id:
        initial["machine"] = machine_id

    source_prediction = None
    prediction_id = request.GET.get("prediction")
    if prediction_id:
        source_prediction = Prediction.objects.filter(pk=prediction_id).first()
        if source_prediction:
            initial["machine"] = source_prediction.machine_id
            initial["title"] = f"Investigate {source_prediction.get_risk_level_display()} risk on {source_prediction.machine.name}"
            initial["priority"] = source_prediction.risk_level if source_prediction.risk_level in ("HIGH", "CRITICAL", "MEDIUM", "LOW") else "MEDIUM"
            initial["description"] = (
                f"Auto-suggested from a {source_prediction.get_risk_level_display()} risk prediction "
                f"({source_prediction.failure_probability:.0%} failure probability) on "
                f"{source_prediction.predicted_at:%Y-%m-%d %H:%M}."
            )

    if request.method == "POST":
        form = MaintenanceRequestForm(request.POST)
        if form.is_valid():
            maintenance_request = form.save(commit=False)
            maintenance_request.requested_by = request.user
            if prediction_id and source_prediction:
                maintenance_request.source_prediction = source_prediction
            maintenance_request.save()
            log_activity(request.user, "CREATE", maintenance_request, request=request)
            messages.success(request, f"Maintenance request '{maintenance_request.title}' created.")
            return redirect("maintenance:detail", pk=maintenance_request.pk)
    else:
        form = MaintenanceRequestForm(initial=initial)

    return render(request, "maintenance/request_form.html", {"form": form})


@login_required
def request_detail(request, pk):
    maintenance_request = get_object_or_404(
        MaintenanceRequest.objects.select_related("machine", "assigned_engineer", "requested_by", "source_prediction"),
        pk=pk,
    )

    context = {
        "maintenance_request": maintenance_request,
        "timeline": build_timeline(maintenance_request),
        "can_assign": _can_assign(request.user),
        "can_schedule": _can_schedule(request.user),
        "can_update_status": _can_update_status(request.user, maintenance_request),
        "assign_form": AssignEngineerForm(),
        "schedule_form": ScheduleForm(),
        "status_form": StatusUpdateForm(initial={"status": maintenance_request.status}),
        "comment_form": CommentForm(),
    }
    return render(request, "maintenance/request_detail.html", context)


# ---------------------------------------------------------------------------
# Actions (all POST-only, redirect back to the detail page)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def request_assign(request, pk):
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    if not _can_assign(request.user):
        messages.error(request, "Only an Admin or Manager can assign an engineer.")
        return redirect("maintenance:detail", pk=pk)

    form = AssignEngineerForm(request.POST)
    if form.is_valid():
        engineer = form.cleaned_data["engineer"]
        assign_engineer(maintenance_request, engineer, assigned_by=request.user)
        messages.success(request, f"Assigned {engineer} to this request.")
    else:
        messages.error(request, "Could not assign engineer — please select a valid engineer.")

    return redirect("maintenance:detail", pk=pk)


@login_required
@require_POST
def request_schedule(request, pk):
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    if not _can_schedule(request.user):
        messages.error(request, "Only an Admin or Manager can schedule maintenance.")
        return redirect("maintenance:detail", pk=pk)
    
    form = ScheduleForm(request.POST)
    if form.is_valid():
        schedule_request(maintenance_request, form.cleaned_data["scheduled_date"], changed_by=request.user)
        messages.success(request, "Schedule updated.")
    else:
        messages.error(request, "Please provide a valid date/time.")

    return redirect("maintenance:detail", pk=pk)


@login_required
@require_POST
def request_update_status(request, pk):
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    if not _can_update_status(request.user, maintenance_request):
        messages.error(request, "You don't have permission to update this request's status.")
        return redirect("maintenance:detail", pk=pk)

    form = StatusUpdateForm(request.POST)
    if form.is_valid():
        change_status(
            maintenance_request, form.cleaned_data["status"], changed_by=request.user, note=form.cleaned_data["note"],
        )
        messages.success(request, "Status updated.")
    else:
        messages.error(request, "Could not update status.")

    return redirect("maintenance:detail", pk=pk)


@login_required
@require_POST
def request_add_comment(request, pk):
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        add_comment(maintenance_request, author=request.user, body=form.cleaned_data["body"])
        messages.success(request, "Comment added.")
    else:
        messages.error(request, "Comment cannot be empty.")

    return redirect("maintenance:detail", pk=pk)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    paginator = Paginator(notifications, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "maintenance/notification_list.html", {"page_obj": page_obj})


@login_required
def api_unread_notification_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"unread_count": count})


@login_required
def api_recent_notifications(request):
    notifications = Notification.objects.filter(user=request.user)[:8]
    return JsonResponse({
        "notifications": [
            {
                "id": n.id, "message": n.message, "link_url": n.link_url,
                "is_read": n.is_read, "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for n in notifications
        ],
        "unread_count": Notification.objects.filter(user=request.user, is_read=False).count(),
    })


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True})
    return redirect(notification.link_url or "maintenance:notification_list")


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True})
    messages.success(request, "All notifications marked as read.")
    return redirect("maintenance:notification_list")
