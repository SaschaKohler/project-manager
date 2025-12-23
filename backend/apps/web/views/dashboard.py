"""
Dashboard and calendar views.
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.projects.models import Project, Task, TaskTimeEntry
from apps.tenants.models import Membership

from .utils import project_span_event_style, task_event_style_for_project, web_shell_context


@login_required
def app_home(request):
    """Main dashboard page."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org

    project_count = org.projects.count()
    task_count = Task.objects.filter(project__organization=org, is_archived=False).count()
    marketing_task_count = org.marketing_tasks.count()

    from apps.tenants.models import OrganizationInvitation
    pending_invitations = OrganizationInvitation.objects.filter(
        email__iexact=request.user.email,
        status=OrganizationInvitation.Status.PENDING,
    ).order_by("-created_at")

    context = {
        **web_shell_context(request),
        "project_count": project_count,
        "task_count": task_count,
        "marketing_task_count": marketing_task_count,
        "pending_invitations": [inv for inv in pending_invitations if not inv.is_expired()],
    }
    return render(request, "web/app/dashboard.html", context)


@login_required
def calendar_page(request):
    """Calendar view page."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    projects = Project.objects.filter(organization=org).order_by("title")
    members = Membership.objects.filter(organization=org).select_related("user")

    context = {
        **web_shell_context(request),
        "projects": projects,
        "members": members,
    }
    return render(request, "web/app/calendar.html", context)


@login_required
def calendar_events(request):
    """API endpoint for calendar events (tasks)."""
    if request.active_org is None:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    org = request.active_org
    start = parse_datetime((request.GET.get("start") or "").strip())
    end = parse_datetime((request.GET.get("end") or "").strip())
    project_id = (request.GET.get("project") or "").strip()
    assigned_to_id = (request.GET.get("assigned_to") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    hide_done = (request.GET.get("hide_done") or "").strip() in {"1", "true", "yes"}

    qs = Task.objects.filter(
        project__organization=org,
        scheduled_start__isnull=False,
        is_archived=False
    )

    if project_id:
        qs = qs.filter(project_id=project_id)
    if assigned_to_id:
        qs = qs.filter(assigned_to_id=assigned_to_id)
    if status in {Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE}:
        qs = qs.filter(status=status)
    if hide_done:
        qs = qs.exclude(status=Task.Status.DONE)
    if start is not None:
        qs = qs.filter(scheduled_start__gte=start)
    if end is not None:
        qs = qs.filter(scheduled_start__lt=end)

    qs = qs.select_related("assigned_to", "project").order_by("scheduled_start")

    events = []
    for task in qs:
        start_dt = task.scheduled_start
        if start_dt is None:
            continue

        duration = task.duration_minutes or 60
        end_dt = start_dt + timedelta(minutes=duration)

        events.append({
            "id": str(task.id),
            "title": f"{task.title} · {task.assigned_to.email}",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "editable": True,
            "durationEditable": True,
            "extendedProps": {
                "status": task.status,
                "assigned_to": str(task.assigned_to_id),
                "assigned_to_email": task.assigned_to.email,
                "task_title": task.title,
                "duration_minutes": duration,
                "project_title": task.project.title,
            },
            **task_event_style_for_project(task.status, getattr(task.project, "color", "")),
        })

    project_qs = Project.objects.filter(organization=org)
    if project_id:
        project_qs = project_qs.filter(id=project_id)
    if start is not None:
        project_qs = project_qs.filter(end_date__gte=start)
    if end is not None:
        project_qs = project_qs.filter(start_date__lt=end)
    project_qs = project_qs.only("id", "title", "start_date", "end_date", "color")

    for project in project_qs:
        start_dt = getattr(project, "start_date", None)
        end_dt = getattr(project, "end_date", None)
        if start_dt is None or end_dt is None:
            continue

        start_local = timezone.localtime(start_dt)
        end_local = timezone.localtime(end_dt)
        start_date = start_local.date()
        end_date = end_local.date()
        if end_date < start_date:
            continue

        events.append({
            "id": f"project-span-{project.id}",
            "title": project.title,
            "start": start_date.isoformat(),
            "end": (end_date + timedelta(days=1)).isoformat(),
            "allDay": True,
            "editable": False,
            "durationEditable": False,
            "extendedProps": {
                "project_id": str(project.id),
                "project_title": project.title,
                "kind": "project_span",
            },
            **project_span_event_style(getattr(project, "color", "")),
        })

    return JsonResponse(events, safe=False)
