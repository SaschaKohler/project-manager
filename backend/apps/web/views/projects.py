"""
Project management views.
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext as _

from apps.projects.models import Project, Task, TaskTimeEntry
from apps.tenants.models import Membership

from .utils import task_event_style, web_shell_context


@login_required
def projects_page(request):
    """List all projects."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    projects = Project.objects.filter(organization=org).order_by("-created_at")

    context = {**web_shell_context(request), "projects": projects}
    return render(request, "web/app/projects/page.html", context)


@login_required
def projects_create(request):
    """Create a new project."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = Membership.objects.filter(organization=org, user=request.user).only("role").first()
    if membership is None or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return redirect("web:projects")

    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip()
    category = (request.POST.get("category") or "").strip().upper()
    priority = (request.POST.get("priority") or "").strip().upper()
    start_date_raw = (request.POST.get("start_date") or "").strip()
    end_date_raw = (request.POST.get("end_date") or "").strip()
    budget_raw = (request.POST.get("budget") or "").strip()

    if not title:
        return redirect("web:projects")

    if category not in dict(Project.Category.choices):
        category = Project.Category.WORKSHOP

    if priority not in dict(Project.Priority.choices):
        priority = Project.Priority.MEDIUM

    start_date = None
    if start_date_raw:
        start_d = parse_date(start_date_raw)
        if start_d:
            from datetime import time
            start_date = timezone.make_aware(timezone.datetime.combine(start_d, time(0, 0)))

    end_date = None
    if end_date_raw:
        end_d = parse_date(end_date_raw)
        if end_d:
            from datetime import time
            end_date = timezone.make_aware(timezone.datetime.combine(end_d, time(23, 59)))

    if start_date is None:
        start_date = timezone.now()
    if end_date is None:
        end_date = start_date + timedelta(days=30)

    budget = None
    if budget_raw:
        try:
            from decimal import Decimal
            budget = Decimal(budget_raw)
        except Exception:  # noqa: BLE001
            pass

    Project.objects.create(
        organization=org,
        title=title,
        description=description,
        category=category,
        priority=priority,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        created_by=request.user,
    )

    return redirect("web:projects")


@login_required
def projects_complete(request, project_id):
    """Mark a project as completed."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist as exc:
        raise Http404() from exc

    project.status = Project.Status.COMPLETED
    project.save(update_fields=["status"])

    return redirect("web:projects")


@login_required
def project_calendar_page(request, project_id):
    """Project-specific calendar view."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist as exc:
        raise Http404() from exc

    members = Membership.objects.filter(organization=org).select_related("user")

    context = {
        **web_shell_context(request),
        "project": project,
        "members": members,
    }
    return render(request, "web/app/projects/calendar.html", context)


@login_required
def project_calendar_events(request, project_id):
    """API endpoint for project calendar events."""
    if request.active_org is None:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    org = request.active_org
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist as exc:
        raise Http404() from exc

    start = parse_datetime((request.GET.get("start") or "").strip())
    end = parse_datetime((request.GET.get("end") or "").strip())
    status = (request.GET.get("status") or "").strip().upper()
    hide_done = (request.GET.get("hide_done") or "").strip() in {"1", "true", "yes"}

    qs = Task.objects.filter(
        project=project, 
        scheduled_start__isnull=False, 
        is_archived=False
    )

    if status in {Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE}:
        qs = qs.filter(status=status)
    if hide_done:
        qs = qs.exclude(status=Task.Status.DONE)
    if start is not None:
        qs = qs.filter(scheduled_start__gte=start)
    if end is not None:
        qs = qs.filter(scheduled_start__lt=end)
    
    qs = qs.select_related("assigned_to").order_by("scheduled_start")

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
            },
            **task_event_style(task.status),
        })

    return JsonResponse(events, safe=False)
