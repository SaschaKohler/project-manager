from django.contrib import messages
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import F
from django.db.models import OuterRef, Subquery
from django.db.models import Q
from django.db.models import Sum
from django.http import Http404
from django.http import HttpResponse, HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone
from django.utils.text import slugify
from datetime import datetime, time, timedelta
from django.utils.translation import gettext as _
from django.db import transaction
from decimal import Decimal
import json

from apps.tenants.models import Membership, Organization, OrganizationInvitation
from apps.projects.models import Project, Task, TaskTimeEntry


def _can_edit_task(request, task: Task) -> bool:
    org = request.active_org
    if org is None:
        return False

    membership = Membership.objects.filter(organization=org, user=request.user).only("role").first()
    if membership is None:
        return False

    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return True

    return task.assigned_to_id == request.user.id


def _require_task_edit_permission(request, task: Task) -> HttpResponse | None:
    if _can_edit_task(request, task):
        return None
    return HttpResponse("", status=403)


def _humanize_seconds(seconds: int) -> str:
    seconds = int(seconds or 0)
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _task_event_style(status: str):
    if status == Task.Status.IN_PROGRESS:
        return {
            "backgroundColor": "rgba(16, 185, 129, 0.85)",
            "borderColor": "rgba(16, 185, 129, 1)",
            "textColor": "rgb(244, 244, 245)",
        }
    if status == Task.Status.DONE:
        return {
            "backgroundColor": "rgba(113, 113, 122, 0.55)",
            "borderColor": "rgba(113, 113, 122, 0.9)",
            "textColor": "rgb(244, 244, 245)",
        }
    return {
        "backgroundColor": "rgba(99, 102, 241, 0.75)",
        "borderColor": "rgba(99, 102, 241, 1)",
        "textColor": "rgb(244, 244, 245)",
    }


def healthz(request):
    return HttpResponse("ok")


@login_required
def app_home(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org

    project_count = org.projects.count()
    task_count = Task.objects.filter(project__organization=org).count()
    marketing_task_count = org.marketing_tasks.count()

    pending_invitations = OrganizationInvitation.objects.filter(
        email__iexact=request.user.email,
        status=OrganizationInvitation.Status.PENDING,
    ).order_by("-created_at")

    context = {
        "org": org,
        "project_count": project_count,
        "task_count": task_count,
        "marketing_task_count": marketing_task_count,
        "pending_invitations": [inv for inv in pending_invitations if not inv.is_expired()],
        "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
    }
    return render(request, "web/app/dashboard.html", context)


def _web_shell_context(request):
    return {
        "org": request.active_org,
        "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
    }


@login_required
def calendar_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    projects = Project.objects.filter(organization=org).order_by("title")
    in_progress_unscheduled = (
        Task.objects.filter(
            project__organization=org,
            status=Task.Status.IN_PROGRESS,
            scheduled_start__isnull=True,
        )
        .select_related("project", "assigned_to")
        .order_by("-updated_at")
    )
    context = {
        **_web_shell_context(request),
        "projects": projects,
        "in_progress_unscheduled": in_progress_unscheduled,
    }
    return render(request, "web/app/calendar.html", context)


@login_required
def calendar_events(request):
    if request.active_org is None:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    org = request.active_org

    start = parse_datetime((request.GET.get("start") or "").strip())
    end = parse_datetime((request.GET.get("end") or "").strip())
    project_id = (request.GET.get("project") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    hide_done = (request.GET.get("hide_done") or "").strip() in {"1", "true", "yes"}

    qs = Task.objects.filter(project__organization=org, scheduled_start__isnull=False)
    if project_id:
        qs = qs.filter(project_id=project_id)
    if status in {Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE}:
        qs = qs.filter(status=status)
    if hide_done:
        qs = qs.exclude(status=Task.Status.DONE)
    if start is not None:
        qs = qs.filter(scheduled_start__gte=start)
    if end is not None:
        qs = qs.filter(scheduled_start__lt=end)
    qs = qs.select_related("project", "assigned_to").order_by("scheduled_start")

    events = []
    for task in qs:
        start_dt = task.scheduled_start
        if start_dt is None:
            continue

        duration = task.duration_minutes or 60
        end_dt = start_dt + timedelta(minutes=duration)

        payload = {
            "id": str(task.id),
            "title": f"{task.project.title}: {task.title} · {task.assigned_to.email}",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "editable": False,
            "durationEditable": False,
            "extendedProps": {
                "project_id": str(task.project_id),
                "project_title": task.project.title,
                "status": task.status,
                "assigned_to": str(task.assigned_to_id),
                "assigned_to_email": task.assigned_to.email,
            },
            **_task_event_style(task.status),
        }
        events.append(payload)

    return JsonResponse(events, safe=False)


@login_required
def team_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    members = Membership.objects.filter(organization=org).select_related("user").order_by("user__email")
    member_user_ids = list(members.values_list("user_id", flat=True))

    User = get_user_model()
    available_users = (
        User.objects.exclude(id__in=member_user_ids)
        .filter(is_active=True)
        .filter(Q(email__isnull=False) & ~Q(email=""))
        .order_by("email")
    )
    invitations = OrganizationInvitation.objects.filter(organization=org, status=OrganizationInvitation.Status.PENDING).order_by(
        "-created_at"
    )

    last_invite_url = request.session.pop("last_invite_url", None)
    context = {
        **_web_shell_context(request),
        "members": members,
        "available_users": available_users,
        "invitations": invitations,
        "last_invite_url": last_invite_url,
    }
    return render(request, "web/app/team/page.html", context)


@login_required
def team_invite(request):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    if not Membership.objects.filter(organization=org, user=request.user).exists():
        raise Http404()

    email = (request.POST.get("email") or "").strip().lower()
    role = (request.POST.get("role") or "").strip().upper() or Membership.Role.MEMBER

    if not email:
        return HttpResponse("", status=400)
    if role not in {Membership.Role.ADMIN, Membership.Role.MEMBER, Membership.Role.OWNER}:
        return HttpResponse("", status=400)

    User = get_user_model()
    existing_user = User.objects.filter(email__iexact=email).first()

    if Membership.objects.filter(organization=org, user__email__iexact=email).exists():
        return redirect("web:team")

    expires_at = timezone.now() + timedelta(days=14)
    invitation = OrganizationInvitation.objects.create(
        organization=org,
        email=email,
        role=role,
        invited_by=request.user,
        expires_at=expires_at,
    )

    invite_url = f"{request.scheme}://{request.get_host()}/app/invite/{invitation.token}/"

    if existing_user is None:
        request.session["last_invite_url"] = invite_url
        send_mail(
            subject=f"Invitation to join {org.name}",
            message=(
                f"You have been invited to join {org.name}.\n\n"
                f"Accept the invitation here:\n{invite_url}\n\n"
                f"This invitation expires on {invitation.expires_at:%Y-%m-%d}."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@localhost",
            recipient_list=[email],
            fail_silently=False,
        )

    return redirect("web:team")


@login_required
def invite_accept(request, token):
    try:
        invitation = OrganizationInvitation.objects.select_related("organization").get(token=token)
    except OrganizationInvitation.DoesNotExist as exc:
        raise Http404() from exc

    if invitation.status != OrganizationInvitation.Status.PENDING:
        raise Http404()
    if invitation.is_expired():
        OrganizationInvitation.objects.filter(id=invitation.id).update(status=OrganizationInvitation.Status.EXPIRED)
        raise Http404()

    if request.method == "GET":
        context = {
            "org": invitation.organization,
            "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
            "invitation": invitation,
        }
        return render(request, "web/app/team/invite_accept.html", context)

    if request.method != "POST":
        raise Http404()

    if request.user.email.lower() != invitation.email.lower():
        return HttpResponse("", status=403)

    with transaction.atomic():
        Membership.objects.get_or_create(
            organization=invitation.organization,
            user=request.user,
            defaults={"role": invitation.role},
        )
        OrganizationInvitation.objects.filter(id=invitation.id).update(
            status=OrganizationInvitation.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )

    request.session["active_org_id"] = str(invitation.organization_id)
    return redirect("web:home")


@login_required
def projects_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    projects = Project.objects.filter(organization=org).order_by("-created_at")
    context = {
        **_web_shell_context(request),
        "projects": projects,
    }
    return render(request, "web/app/projects/page.html", context)


@login_required
def projects_create(request):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip() or None
    status = (request.POST.get("status") or "").strip() or Project.Status.PLANNED
    category = (request.POST.get("category") or "").strip() or Project.Category.WORKSHOP
    priority = (request.POST.get("priority") or "").strip() or Project.Priority.MEDIUM
    budget_raw = (request.POST.get("budget") or "").strip()
    start_raw = (request.POST.get("start_date") or "").strip()
    end_raw = (request.POST.get("end_date") or "").strip()

    if not title:
        return HttpResponse("", status=400)

    if status not in {Project.Status.PLANNED, Project.Status.ACTIVE, Project.Status.COMPLETED, Project.Status.CANCELLED}:
        return HttpResponse("", status=400)
    if category not in {c for c, _ in Project.Category.choices}:
        return HttpResponse("", status=400)
    if priority not in {Project.Priority.LOW, Project.Priority.MEDIUM, Project.Priority.HIGH}:
        return HttpResponse("", status=400)

    start_dt = parse_datetime(start_raw) if start_raw else None
    end_dt = parse_datetime(end_raw) if end_raw else None
    if start_dt is None and start_raw:
        start_d = parse_date(start_raw)
        if start_d is not None:
            start_dt = datetime.combine(start_d, time(9, 0))
    if end_dt is None and end_raw:
        end_d = parse_date(end_raw)
        if end_d is not None:
            end_dt = datetime.combine(end_d, time(17, 0))
    if start_dt is not None and timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt)
    if end_dt is not None and timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt)

    if start_dt is None:
        start_dt = timezone.now()
    if end_dt is None:
        end_dt = start_dt + timedelta(days=7)
    if end_dt < start_dt:
        return HttpResponse("", status=400)

    budget = None
    if budget_raw:
        try:
            budget = Decimal(budget_raw)
        except Exception:
            return HttpResponse("", status=400)

    project = Project.objects.create(
        organization=request.active_org,
        title=title,
        description=description,
        status=status,
        start_date=start_dt,
        end_date=end_dt,
        category=category,
        budget=budget,
        priority=priority,
        created_by=request.user,
    )

    if request.headers.get("HX-Request") == "true":
        return render(request, "web/app/projects/_project_row.html", {"project": project})

    return redirect("web:projects")


@login_required
def project_calendar_page(request, project_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist as exc:
        raise Http404() from exc

    unscheduled_tasks = (
        Task.objects.filter(project=project, scheduled_start__isnull=True)
        .select_related("assigned_to")
        .order_by("status", "sort_order", "-created_at")
    )
    in_progress_unscheduled = (
        Task.objects.filter(project=project, scheduled_start__isnull=True, status=Task.Status.IN_PROGRESS)
        .select_related("assigned_to")
        .order_by("-updated_at")
    )

    context = {
        **_web_shell_context(request),
        "project": project,
        "unscheduled_tasks": unscheduled_tasks,
        "in_progress_unscheduled": in_progress_unscheduled,
    }
    return render(request, "web/app/projects/calendar.html", context)


@login_required
def project_calendar_events(request, project_id):
    if request.active_org is None:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    org = request.active_org
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist as exc:
        raise Http404() from exc

    start = parse_datetime((request.GET.get("start") or "").strip())
    end = parse_datetime((request.GET.get("end") or "").strip())

    qs = Task.objects.filter(project=project, scheduled_start__isnull=False)

    status = (request.GET.get("status") or "").strip().upper()
    hide_done = (request.GET.get("hide_done") or "").strip() in {"1", "true", "yes"}

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

        payload = {
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
            **_task_event_style(task.status),
        }
        events.append(payload)

    return JsonResponse(events, safe=False)


@login_required
def tasks_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    view = (request.GET.get("view") or "all").strip().lower()
    project_id = (request.GET.get("project") or "").strip()
    projects = Project.objects.filter(organization=org).order_by("title")
    members = Membership.objects.filter(organization=org).select_related("user").order_by("user__email")
    open_started_at_subquery = Subquery(
        TaskTimeEntry.objects.filter(task_id=OuterRef("pk"), user=request.user, stopped_at__isnull=True)
        .order_by("-started_at")
        .values("started_at")[:1]
    )

    tasks = (
        Task.objects.filter(project__organization=org)
        .select_related("project", "assigned_to")
        .annotate(running_started_at=open_started_at_subquery)
    )

    active_project = None
    if project_id:
        try:
            active_project = Project.objects.get(id=project_id, organization=org)
        except Project.DoesNotExist:
            active_project = None
    if active_project is not None:
        tasks = tasks.filter(project=active_project)

    if view == "inbox":
        tasks = tasks.filter(status=Task.Status.TODO)
    elif view == "today":
        today = timezone.localdate()
        tasks = tasks.filter(due_date__date=today).exclude(status=Task.Status.DONE)
    else:
        view = "all"

    todo_tasks = tasks.filter(status=Task.Status.TODO).order_by("sort_order", "-created_at")
    in_progress_tasks = tasks.filter(status=Task.Status.IN_PROGRESS).order_by("sort_order", "-created_at")
    done_tasks = tasks.filter(status=Task.Status.DONE).order_by("sort_order", "-created_at")

    running_task_ids = list(tasks.filter(running_started_at__isnull=False).values_list("id", flat=True))

    done_total_seconds = int(done_tasks.aggregate(total=Sum("tracked_seconds")).get("total") or 0)
    done_total_human = _humanize_seconds(done_total_seconds)

    project_time_overview = []
    active_project_total_seconds = 0
    active_project_total_human = _humanize_seconds(0)
    active_project_top_tasks = []

    if active_project is not None:
        active_project_total_seconds = int(
            Task.objects.filter(project=active_project).aggregate(total=Sum("tracked_seconds")).get("total") or 0
        )
        active_project_total_human = _humanize_seconds(active_project_total_seconds)
        active_project_top_tasks = list(
            Task.objects.filter(project=active_project)
            .exclude(tracked_seconds=0)
            .order_by("-tracked_seconds")[:5]
        )
    else:
        rows = (
            Task.objects.filter(project__organization=org)
            .values("project_id", "project__title")
            .annotate(total_seconds=Sum("tracked_seconds"))
            .order_by("-total_seconds", "project__title")
        )
        for r in rows:
            total = int(r.get("total_seconds") or 0)
            project_time_overview.append(
                {
                    "project_id": r["project_id"],
                    "project_title": r["project__title"],
                    "total_seconds": total,
                    "total_human": _humanize_seconds(total),
                }
            )

    context = {
        **_web_shell_context(request),
        "projects": projects,
        "members": members,
        "todo_tasks": todo_tasks,
        "in_progress_tasks": in_progress_tasks,
        "done_tasks": done_tasks,
        "running_task_ids": running_task_ids,
        "done_total_seconds": done_total_seconds,
        "done_total_human": done_total_human,
        "project_time_overview": project_time_overview,
        "active_project_total_seconds": active_project_total_seconds,
        "active_project_total_human": active_project_total_human,
        "active_project_top_tasks": active_project_top_tasks,
        "active_view": view,
        "active_project": active_project,
    }
    return render(request, "web/app/tasks/page.html", context)


def _normalize_column_order(org, status):
    qs = Task.objects.filter(project__organization=org, status=status).order_by("sort_order", "-created_at")
    for idx, task in enumerate(qs):
        if task.sort_order != idx:
            Task.objects.filter(id=task.id).update(sort_order=idx)


def _insert_task_at_position(org, task: Task, new_status: str, position: int):
    ids = list(
        Task.objects.filter(project__organization=org, status=new_status)
        .order_by("sort_order", "-created_at")
        .values_list("id", flat=True)
    )

    if task.id in ids:
        ids.remove(task.id)

    position = max(0, min(position, len(ids)))
    ids.insert(position, task.id)

    for idx, task_id in enumerate(ids):
        Task.objects.filter(id=task_id).update(sort_order=idx)


@login_required
def tasks_create(request):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    title = (request.POST.get("title") or "").strip()
    project_id = (request.POST.get("project_id") or "").strip()
    assigned_to_id = (request.POST.get("assigned_to") or "").strip()
    if not title or not project_id:
        return HttpResponse("", status=400)

    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist:
        return HttpResponse("", status=400)

    assigned_to = request.user
    if assigned_to_id:
        if not Membership.objects.filter(organization=org, user_id=assigned_to_id).exists():
            return HttpResponse("", status=400)
        assigned_to = Membership.objects.get(organization=org, user_id=assigned_to_id).user

    task = Task.objects.create(
        project=project,
        title=title,
        assigned_to=assigned_to,
        status=Task.Status.TODO,
    )

    if task.assigned_to_id != request.user.id:
        Task.objects.filter(id=task.id).update(sort_order=0)

    _normalize_column_order(org, Task.Status.TODO)

    if request.headers.get("HX-Request") == "true":
        members = Membership.objects.filter(organization=org).select_related("user").order_by("user__email")
        return render(
            request,
            "web/app/tasks/_task_card.html",
            {"task": task, "members": members, "running_task_ids": []},
        )

    return redirect("web:tasks")


@login_required
def tasks_time_entries(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "GET":
        raise Http404()

    org = request.active_org
    if not Membership.objects.filter(organization=org, user=request.user).exists():
        return HttpResponse("", status=403)

    try:
        task = Task.objects.select_related("project").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    if task.status != Task.Status.DONE:
        return HttpResponse("", status=400)

    entries = (
        TaskTimeEntry.objects.filter(task=task)
        .select_related("user")
        .order_by("-started_at")
    )

    entry_items = []
    for e in entries:
        started = timezone.localtime(e.started_at) if e.started_at else None
        stopped = timezone.localtime(e.stopped_at) if e.stopped_at else None
        duration = int(e.duration_seconds or 0)
        entry_items.append(
            {
                "id": e.id,
                "user_email": getattr(e.user, "email", ""),
                "started_at": started,
                "stopped_at": stopped,
                "duration_seconds": duration,
                "duration_human": _humanize_seconds(duration),
            }
        )

    total_seconds = int(task.tracked_seconds or 0)
    context = {
        "task": task,
        "entries": entry_items,
        "total_seconds": total_seconds,
        "total_human": _humanize_seconds(total_seconds),
    }
    return render(request, "web/app/tasks/_task_time_entries.html", context)


@login_required
def tasks_assign(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project", "assigned_to").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    assigned_to_id = (request.POST.get("assigned_to") or "").strip()
    assigned_to = request.user
    if assigned_to_id:
        if not Membership.objects.filter(organization=org, user_id=assigned_to_id).exists():
            return HttpResponse("", status=400)
        assigned_to = Membership.objects.get(organization=org, user_id=assigned_to_id).user

    if task.assigned_to_id != assigned_to.id:
        Task.objects.filter(id=task.id).update(assigned_to=assigned_to)
        task.assigned_to = assigned_to

    members = Membership.objects.filter(organization=org).select_related("user").order_by("user__email")
    if request.headers.get("HX-Request") == "true":
        started_at = (
            TaskTimeEntry.objects.filter(task_id=task.id, user=request.user, stopped_at__isnull=True)
            .order_by("-started_at")
            .values_list("started_at", flat=True)
            .first()
        )
        running_task_ids = [task.id] if started_at else []
        task.running_started_at = started_at
        return render(
            request,
            "web/app/tasks/_task_card.html",
            {"task": task, "members": members, "running_task_ids": running_task_ids},
        )

    return redirect("web:tasks")


@login_required
def tasks_schedule(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    start_raw = (request.POST.get("start") or "").strip()
    end_raw = (request.POST.get("end") or "").strip()

    start_dt = parse_datetime(start_raw) if start_raw else None
    end_dt = parse_datetime(end_raw) if end_raw else None
    if start_dt is None:
        return HttpResponse("", status=400)

    duration_minutes = None
    if end_dt is not None:
        diff = end_dt - start_dt
        duration_minutes = max(1, int((diff.total_seconds() + 59) // 60))
    else:
        try:
            duration_minutes = int(request.POST.get("duration_minutes") or "")
        except ValueError:
            duration_minutes = None

    if duration_minutes is None:
        duration_minutes = task.duration_minutes or 60

    Task.objects.filter(id=task.id).update(
        scheduled_start=start_dt,
        duration_minutes=duration_minutes,
        due_date=start_dt,
    )

    return HttpResponse("", status=204)


@login_required
def tasks_unschedule(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    clear_due = (request.POST.get("clear_due_date") or "").strip() in {"1", "true", "yes"}

    update_fields = {
        "scheduled_start": None,
        "duration_minutes": None,
    }
    if clear_due:
        update_fields["due_date"] = None

    Task.objects.filter(id=task.id).update(**update_fields)
    return HttpResponse("", status=204)


@login_required
def tasks_title(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    try:
        task = Task.objects.select_related("project", "assigned_to").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    if request.method == "GET":
        mode = (request.GET.get("mode") or "view").strip().lower()
        if mode == "edit":
            return render(request, "web/app/tasks/_task_title_edit.html", {"task": task})
        return render(request, "web/app/tasks/_task_title.html", {"task": task})

    if request.method != "POST":
        raise Http404()

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    title = (request.POST.get("title") or "").strip()
    if title:
        Task.objects.filter(id=task.id).update(title=title)
        task.title = title

    if request.headers.get("HX-Request") == "true":
        return render(request, "web/app/tasks/_task_title.html", {"task": task})

    return redirect("web:tasks")


@login_required
def tasks_move(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    new_status = (request.POST.get("status") or "").strip()
    try:
        position = int(request.POST.get("position", "0"))
    except ValueError:
        position = 0

    if new_status not in {Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE}:
        return HttpResponse("", status=400)

    old_status = task.status

    with transaction.atomic():
        if old_status != new_status:
            task.status = new_status
            task.save(update_fields=["status", "updated_at"])

        _insert_task_at_position(org, task, new_status, position)
        _normalize_column_order(org, new_status)
        if old_status != new_status:
            _normalize_column_order(org, old_status)

    return HttpResponse("", status=204)


@login_required
def tasks_toggle(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    old_status = task.status
    new_status = Task.Status.DONE if task.status != Task.Status.DONE else Task.Status.TODO

    with transaction.atomic():
        task.status = new_status
        task.save(update_fields=["status", "updated_at"])

        if new_status == Task.Status.DONE:
            now = timezone.now()
            open_entries = list(TaskTimeEntry.objects.filter(task=task, stopped_at__isnull=True))
            total_added = 0
            for entry in open_entries:
                delta = now - entry.started_at
                added = max(0, int(delta.total_seconds()))
                if added:
                    TaskTimeEntry.objects.filter(id=entry.id).update(stopped_at=now, duration_seconds=entry.duration_seconds + added)
                    total_added += added
                else:
                    TaskTimeEntry.objects.filter(id=entry.id).update(stopped_at=now)

            if total_added:
                Task.objects.filter(id=task.id).update(tracked_seconds=F("tracked_seconds") + total_added)

        _normalize_column_order(org, new_status)
        if old_status != new_status:
            _normalize_column_order(org, old_status)

    if request.headers.get("HX-Request") == "true":
        members = Membership.objects.filter(organization=org).select_related("user").order_by("user__email")
        task.refresh_from_db(fields=["tracked_seconds"])
        started_at = (
            TaskTimeEntry.objects.filter(task_id=task.id, user=request.user, stopped_at__isnull=True)
            .order_by("-started_at")
            .values_list("started_at", flat=True)
            .first()
        )
        running_task_ids = [task.id] if started_at else []
        task.running_started_at = started_at
        response = render(
            request,
            "web/app/tasks/_task_card.html",
            {"task": task, "members": members, "running_task_ids": running_task_ids},
        )
        response["HX-Trigger"] = json.dumps(
            {
                "taskStatusChanged": {
                    "task_id": str(task.id),
                    "new_status": new_status,
                }
            }
        )
        return response

    return redirect("web:tasks")


@login_required
def tasks_timer(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    now = timezone.now()
    open_entry = (
        TaskTimeEntry.objects.filter(task=task, user=request.user, stopped_at__isnull=True)
        .order_by("-started_at")
        .first()
    )

    if open_entry is None:
        if task.status == Task.Status.TODO:
            Task.objects.filter(id=task.id).update(status=Task.Status.IN_PROGRESS)
            task.status = Task.Status.IN_PROGRESS

        TaskTimeEntry.objects.create(task=task, user=request.user, started_at=now)
    else:
        delta = now - open_entry.started_at
        added = max(0, int(delta.total_seconds()))
        TaskTimeEntry.objects.filter(id=open_entry.id).update(
            stopped_at=now,
            duration_seconds=open_entry.duration_seconds + added,
        )
        if added:
            Task.objects.filter(id=task.id).update(tracked_seconds=F("tracked_seconds") + added)
            task.refresh_from_db(fields=["tracked_seconds"])

    if request.headers.get("HX-Request") == "true":
        members = Membership.objects.filter(organization=org).select_related("user").order_by("user__email")
        started_at = (
            TaskTimeEntry.objects.filter(task_id=task.id, user=request.user, stopped_at__isnull=True)
            .order_by("-started_at")
            .values_list("started_at", flat=True)
            .first()
        )
        running_task_ids = [task.id] if started_at else []
        task.running_started_at = started_at
        return render(
            request,
            "web/app/tasks/_task_card.html",
            {"task": task, "members": members, "running_task_ids": running_task_ids},
        )

    return redirect("web:tasks")


@login_required
def onboarding(request):
    if request.active_org is not None:
        return redirect("web:home")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, _("Please provide a workspace name"))
            return render(request, "web/app/onboarding.html")

        base_slug = slugify(name) or "workspace"
        slug = base_slug
        idx = 1
        while Organization.objects.filter(slug=slug).exists():
            idx += 1
            slug = f"{base_slug}-{idx}"

        org = Organization.objects.create(name=name, slug=slug)
        Membership.objects.create(organization=org, user=request.user, role=Membership.Role.OWNER)
        request.session["active_org_id"] = str(org.id)

        return redirect("web:home")

    return render(request, "web/app/onboarding.html")


@login_required
def workspaces_new(request):
    if request.method == "GET":
        return render(request, "web/app/workspaces/new.html", {**_web_shell_context(request)})

    if request.method != "POST":
        raise Http404()

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, _("Please provide a workspace name"))
        return render(request, "web/app/workspaces/new.html", {**_web_shell_context(request)})

    base_slug = slugify(name) or "workspace"
    slug = base_slug
    idx = 1
    while Organization.objects.filter(slug=slug).exists():
        idx += 1
        slug = f"{base_slug}-{idx}"

    org = Organization.objects.create(name=name, slug=slug)
    Membership.objects.create(organization=org, user=request.user, role=Membership.Role.OWNER)
    request.session["active_org_id"] = str(org.id)
    return redirect("web:home")


@login_required
def switch_org(request, org_id):
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist as exc:
        raise Http404() from exc

    if not Membership.objects.filter(user=request.user, organization=org).exists():
        raise Http404()

    request.session["active_org_id"] = str(org.id)
    return redirect("web:home")
