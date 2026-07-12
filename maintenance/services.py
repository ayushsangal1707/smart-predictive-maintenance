"""
maintenance/services.py
-------------------------
Business logic for maintenance requests, kept separate from views.py so
each action (assign, change status, schedule, comment) has one obvious
place to test and reuse — every one of these functions both mutates the
request and creates the appropriate Notification(s) in a single call, so
a view can never accidentally do one without the other.
"""

from django.utils import timezone

from core.email_utils import send_alert_email

from .models import Comment, Notification, STATUS_COMPLETED, StatusHistory


def notify(user, message, link_url=""):
    """Creates a Notification for `user`, or does nothing if user is None
    (e.g. a request with no assigned engineer yet)."""
    if user is None:
        return None
    return Notification.objects.create(user=user, message=message, link_url=link_url)


def _interested_parties(request_obj, exclude_user=None):
    """Everyone who should hear about an update to this request, minus
    whoever just performed the action (no one needs to be notified about
    their own change)."""
    parties = {request_obj.requested_by, request_obj.assigned_engineer}
    parties.discard(None)
    parties.discard(exclude_user)
    return parties


def assign_engineer(request_obj, engineer, assigned_by):
    """
    Assigns `engineer` to `request_obj`. If the request is still in the
    initial OPEN status, this also advances it to ASSIGNED (an assigned
    request that's still "Open" would be a confusing state to show users).
    """
    request_obj.assigned_engineer = engineer
    if request_obj.status == "OPEN":
        change_status(request_obj, "ASSIGNED", changed_by=assigned_by, note="Auto-advanced on assignment", _skip_save=True)
    request_obj.save()

    link = request_obj.get_absolute_url()
    notify(engineer, f"You were assigned to maintenance request: {request_obj.title}", link)
    send_alert_email(
        engineer,
        subject=f"Maintenance Assignment: {request_obj.title}",
        message=(
            f"You have been assigned to a maintenance request on {request_obj.machine.name} "
            f"({request_obj.machine.machine_code}).\n\nTitle: {request_obj.title}\n"
            f"Priority: {request_obj.get_priority_display()}\n\n{request_obj.description}"
        ),
    )
    for user in _interested_parties(request_obj, exclude_user=assigned_by) - {engineer}:
        notify(user, f"{engineer} was assigned to: {request_obj.title}", link)

    return request_obj


def change_status(request_obj, new_status, changed_by, note="", _skip_save=False):
    """
    Records the transition in StatusHistory, updates the request's status
    (and completed_at if moving to COMPLETED), and notifies everyone
    involved except whoever made the change.

    `_skip_save` is an internal flag used by assign_engineer() above, which
    calls this mid-way through its own save() — avoids a redundant double
    save() when both the assignment and the auto status-advance happen in
    the same request/response cycle.
    """
    old_status = request_obj.status
    request_obj.status = new_status

    if new_status == STATUS_COMPLETED and request_obj.completed_at is None:
        request_obj.completed_at = timezone.now()

    if not _skip_save:
        request_obj.save()

    StatusHistory.objects.create(
        request=request_obj, old_status=old_status, new_status=new_status, changed_by=changed_by, note=note,
    )

    link = request_obj.get_absolute_url()
    display = dict(request_obj._meta.get_field("status").choices).get(new_status, new_status)
    for user in _interested_parties(request_obj, exclude_user=changed_by):
        notify(user, f"Status changed to '{display}' for: {request_obj.title}", link)

    return request_obj


def schedule_request(request_obj, scheduled_date, changed_by):
    request_obj.scheduled_date = scheduled_date
    request_obj.save()

    link = request_obj.get_absolute_url()
    for user in _interested_parties(request_obj, exclude_user=changed_by):
        notify(user, f"Maintenance scheduled for {scheduled_date:%Y-%m-%d %H:%M}: {request_obj.title}", link)

    return request_obj


def add_comment(request_obj, author, body):
    comment = Comment.objects.create(request=request_obj, author=author, body=body)

    link = request_obj.get_absolute_url()
    for user in _interested_parties(request_obj, exclude_user=author):
        notify(user, f"{author} commented on: {request_obj.title}", link)

    return comment


def build_timeline(request_obj):
    """
    Merges StatusHistory + Comment into one chronological list for the
    detail page's "History" section, since the prompt asks for a unified
    history view rather than two separate disconnected lists.
    """
    events = []
    for h in request_obj.status_history.select_related("changed_by").all():
        events.append({"type": "status", "at": h.changed_at, "obj": h})
    for c in request_obj.comments.select_related("author").all():
        events.append({"type": "comment", "at": c.created_at, "obj": c})
    events.sort(key=lambda e: e["at"])
    return events
