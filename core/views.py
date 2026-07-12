from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.dateparse import parse_date

from accounts.decorators import role_required
from core.constants import ROLE_ADMIN

from .models import ACTION_CHOICES, AuditLog

PAGE_SIZE = 30


@role_required(ROLE_ADMIN)
def audit_log_list(request):
    logs = AuditLog.objects.select_related("user")

    query = request.GET.get("q", "").strip()
    action = request.GET.get("action", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    if query:
        logs = (
            logs.filter(user__username__icontains=query)
            | logs.filter(object_repr__icontains=query)
            | logs.filter(description__icontains=query)
        )
    if action:
        logs = logs.filter(action=action)
    if date_from:
        parsed = parse_date(date_from)
        if parsed:
            logs = logs.filter(created_at__date__gte=parsed)
    if date_to:
        parsed = parse_date(date_to)
        if parsed:
            logs = logs.filter(created_at__date__lte=parsed)

    paginator = Paginator(logs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    querydict = request.GET.copy()
    querydict.pop("page", None)
    querystring = querydict.urlencode()

    return render(request, "core/audit_log_list.html", {
        "page_obj": page_obj,
        "query": query,
        "action": action,
        "date_from": date_from,
        "date_to": date_to,
        "querystring": querystring,
        "action_choices": ACTION_CHOICES,
        "total_count": paginator.count,
    })
