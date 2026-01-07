from django.contrib import messages
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import F
from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models import Q
from django.db.models import Sum, Max
from django.http import Http404
from django.http import HttpResponse, HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone
from django.utils.html import escape
from django.utils.text import slugify
from datetime import datetime, time, timedelta
from django.utils.translation import gettext as _
from decimal import Decimal
import json

from apps.accounts.forms import CustomUserCreationForm
from apps.boards.models import (
    AutomationAction,
    AutomationRule,
    Board,
    BoardCard,
    BoardCardAttachment,
    BoardCardLabel,
    BoardCardLink,
    BoardColumn,
    CardButton,
    CardButtonAction,
)
from apps.boards.automation import AutomationEngine, execute_card_button
from apps.tenants.models import Membership, Organization, OrganizationInvitation
from apps.projects.models import (
    Project,
    Task,
    TaskAutomationAction,
    TaskAutomationRule,
    TaskButton,
    TaskButtonAction,
    TaskLabel,
    TaskLabelAssignment,
    TaskLink,
    TaskTimeEntry,
)
from apps.projects.automation import TaskAutomationEngine, execute_task_button


def _can_edit_task(request, task: Task) -> bool:
    org = request.active_org
    if org is None:
        return False

    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None:
        return False

    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return True

    if getattr(task, "idea_card_id", None):
        try:
            if (
                task.idea_card
                and getattr(task.idea_card, "created_by_id", None) == request.user.id
            ):
                return True
        except Exception:  # noqa: BLE001
            pass

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


def _project_event_style(color: str):
    palette = {
        "indigo": (
            "rgba(99, 102, 241, 0.30)",
            "rgba(99, 102, 241, 0.85)",
            "rgb(224, 231, 255)",
        ),
        "emerald": (
            "rgba(16, 185, 129, 0.28)",
            "rgba(16, 185, 129, 0.85)",
            "rgb(209, 250, 229)",
        ),
        "sky": (
            "rgba(14, 165, 233, 0.28)",
            "rgba(14, 165, 233, 0.85)",
            "rgb(224, 242, 254)",
        ),
        "violet": (
            "rgba(139, 92, 246, 0.28)",
            "rgba(139, 92, 246, 0.85)",
            "rgb(237, 233, 254)",
        ),
        "rose": (
            "rgba(244, 63, 94, 0.26)",
            "rgba(244, 63, 94, 0.85)",
            "rgb(255, 228, 230)",
        ),
        "amber": (
            "rgba(245, 158, 11, 0.26)",
            "rgba(245, 158, 11, 0.85)",
            "rgb(254, 243, 199)",
        ),
        "teal": (
            "rgba(20, 184, 166, 0.26)",
            "rgba(20, 184, 166, 0.85)",
            "rgb(204, 251, 241)",
        ),
        "orange": (
            "rgba(249, 115, 22, 0.26)",
            "rgba(249, 115, 22, 0.85)",
            "rgb(255, 237, 213)",
        ),
        "lime": (
            "rgba(132, 204, 22, 0.24)",
            "rgba(132, 204, 22, 0.85)",
            "rgb(236, 252, 203)",
        ),
        "fuchsia": (
            "rgba(217, 70, 239, 0.26)",
            "rgba(217, 70, 239, 0.85)",
            "rgb(250, 232, 255)",
        ),
    }
    bg, border, text = palette.get((color or "").strip().lower(), palette["indigo"])
    return {
        "backgroundColor": bg,
        "borderColor": border,
        "textColor": text,
    }


def healthz(request):
    return HttpResponse("ok")


def register(request):
    if request.user.is_authenticated:
        return redirect("web:onboarding")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("web:onboarding")
    else:
        form = CustomUserCreationForm()

    return render(request, "web/auth/register.html", {"form": form})


@login_required
def app_home(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org

    project_count = org.projects.count()
    task_count = Task.objects.filter(
        project__organization=org, is_archived=False
    ).count()
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
        "pending_invitations": [
            inv for inv in pending_invitations if not inv.is_expired()
        ],
        "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
    }
    return render(request, "web/app/dashboard.html", context)


def _web_shell_context(request):
    membership = None
    if request.active_org is not None:
        membership = (
            Membership.objects.filter(
                organization=request.active_org, user=request.user
            )
            .only("role")
            .first()
        )

    is_owner = bool(membership and membership.role == Membership.Role.OWNER)

    return {
        "org": request.active_org,
        "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
        "is_owner": is_owner,
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
            is_archived=False,
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

    qs = Task.objects.filter(
        project__organization=org, scheduled_start__isnull=False, is_archived=False
    )
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

        payload = {
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
            **_project_event_style(getattr(project, "color", "")),
        }
        events.append(payload)

    for project in project_qs:
        end_dt = project.end_date
        if end_dt is None:
            continue
        end_local = timezone.localtime(end_dt)
        end_date = end_local.date()
        payload = {
            "id": f"project-deadline-{project.id}",
            "title": f"{project.title} · Deadline",
            "start": end_date.isoformat(),
            "end": (end_date + timedelta(days=1)).isoformat(),
            "allDay": True,
            "editable": False,
            "durationEditable": False,
            "extendedProps": {
                "project_id": str(project.id),
                "project_title": project.title,
                "kind": "project_deadline",
            },
            **_project_event_style(getattr(project, "color", "")),
        }
        events.append(payload)

    return JsonResponse(events, safe=False)


@login_required
def boards_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    boards = Board.objects.filter(organization=request.active_org).order_by("title")
    context = {
        **_web_shell_context(request),
        "boards": boards,
    }
    return render(request, "web/app/boards/page.html", context)


@login_required
def boards_create(request):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    title = (request.POST.get("title") or "").strip()
    if not title:
        return HttpResponse("", status=400)

    board = Board.objects.create(
        organization=request.active_org,
        title=title,
        created_by=request.user,
    )

    BoardColumn.objects.bulk_create(
        [
            BoardColumn(board=board, title=_("Ideas"), sort_order=0),
            BoardColumn(board=board, title=_("In review"), sort_order=1),
            BoardColumn(board=board, title=_("Planned"), sort_order=2),
            BoardColumn(board=board, title=_("Done"), sort_order=3),
        ]
    )

    return redirect("web:board_detail", board_id=board.id)


@login_required
def board_detail_page(request, board_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    columns = (
        BoardColumn.objects.filter(board=board)
        .prefetch_related(
            Prefetch(
                "cards",
                queryset=BoardCard.objects.all().prefetch_related(
                    "links", "attachments"
                ),
            )
        )
        .order_by("sort_order", "title")
    )

    context = {
        **_web_shell_context(request),
        "board": board,
        "columns": columns,
    }
    return render(request, "web/app/boards/detail.html", context)


@login_required
def board_card_create(request, board_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    column_id = (request.POST.get("column_id") or "").strip()
    title = (request.POST.get("title") or "").strip()
    if not column_id or not title:
        return HttpResponse("", status=400)

    column = BoardColumn.objects.filter(id=column_id, board=board).first()
    if column is None:
        return HttpResponse("", status=400)

    max_sort = (
        BoardCard.objects.filter(column=column)
        .aggregate(max=Max("sort_order"))
        .get("max")
    )
    sort_order = int(max_sort or 0) + 1

    card = BoardCard.objects.create(
        column=column,
        title=title,
        sort_order=sort_order,
        created_by=request.user,
    )

    # Trigger automation rules for card_created
    engine = AutomationEngine(triggered_by=request.user)
    engine.trigger_card_created(card)

    return redirect("web:board_detail", board_id=board.id)


@login_required
def board_card_detail(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    try:
        card = (
            BoardCard.objects.select_related("column__board")
            .prefetch_related("links", "attachments")
            .get(id=card_id, column__board__organization=request.active_org)
        )
    except BoardCard.DoesNotExist as exc:
        raise Http404() from exc

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        if not title:
            return HttpResponse("", status=400)

        BoardCard.objects.filter(id=card.id).update(
            title=title, description=description
        )
        return redirect("web:board_card_detail", card_id=card.id)

    context = {
        **_web_shell_context(request),
        "card": card,
        "board": card.column.board,
    }
    return render(request, "web/app/boards/card_detail.html", context)


@login_required
def board_card_link_create(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(
            id=card_id,
            column__board__organization=request.active_org,
        )
        .first()
    )
    if card is None:
        raise Http404()

    url = (request.POST.get("url") or "").strip()
    title = (request.POST.get("title") or "").strip()
    if not url:
        return HttpResponse("", status=400)

    BoardCardLink.objects.create(card=card, url=url, title=title)
    return redirect("web:board_card_detail", card_id=card.id)


@login_required
def board_card_attachment_create(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(
            id=card_id,
            column__board__organization=request.active_org,
        )
        .first()
    )
    if card is None:
        raise Http404()

    f = request.FILES.get("file")
    if f is None:
        return HttpResponse("", status=400)

    BoardCardAttachment.objects.create(card=card, file=f, uploaded_by=request.user)
    return redirect("web:board_card_detail", card_id=card.id)


@login_required
def board_card_move(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    if not Membership.objects.filter(organization=org, user=request.user).exists():
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(
            id=card_id,
            column__board__organization=org,
        )
        .first()
    )
    if card is None:
        raise Http404()

    column_id = (request.POST.get("column_id") or "").strip()
    if not column_id:
        return HttpResponse("", status=400)

    target_col = BoardColumn.objects.filter(
        id=column_id, board=card.column.board
    ).first()
    if target_col is None:
        return HttpResponse("", status=400)

    if target_col.id == card.column_id:
        return redirect("web:board_detail", board_id=card.column.board_id)

    from_column = card.column
    max_sort = (
        BoardCard.objects.filter(column=target_col)
        .aggregate(max=Max("sort_order"))
        .get("max")
    )
    sort_order = int(max_sort or 0) + 1
    BoardCard.objects.filter(id=card.id).update(
        column=target_col, sort_order=sort_order
    )

    # Trigger automation rules for card_moved
    card.refresh_from_db()
    engine = AutomationEngine(triggered_by=request.user)
    engine.trigger_card_moved(card, from_column=from_column, to_column=target_col)

    return redirect("web:board_detail", board_id=card.column.board_id)


@login_required
def board_automations_page(request, board_id):
    """List all automation rules for a board."""
    if request.active_org is None:
        return redirect("web:onboarding")

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    rules = (
        AutomationRule.objects.filter(board=board)
        .prefetch_related("actions")
        .order_by("-created_at")
    )
    buttons = (
        CardButton.objects.filter(board=board)
        .prefetch_related("actions")
        .order_by("name")
    )
    labels = BoardCardLabel.objects.filter(board=board).order_by("name")

    context = {
        **_web_shell_context(request),
        "board": board,
        "rules": rules,
        "buttons": buttons,
        "labels": labels,
        "trigger_types": AutomationRule.TriggerType.choices,
        "action_types": AutomationAction.ActionType.choices,
    }
    return render(request, "web/app/boards/automations.html", context)


@login_required
def board_automation_rule_create(request, board_id):
    """Create a new automation rule."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    name = (request.POST.get("name") or "").strip()
    trigger_type = (request.POST.get("trigger_type") or "").strip()
    description = (request.POST.get("description") or "").strip()

    if not name or trigger_type not in dict(AutomationRule.TriggerType.choices):
        return HttpResponse("", status=400)

    # Build trigger config from form
    trigger_config = {}
    to_column_id = (request.POST.get("to_column_id") or "").strip()
    from_column_id = (request.POST.get("from_column_id") or "").strip()
    label_id = (request.POST.get("trigger_label_id") or "").strip()

    if to_column_id:
        trigger_config["to_column_id"] = to_column_id
    if from_column_id:
        trigger_config["from_column_id"] = from_column_id
    if label_id:
        trigger_config["label_id"] = label_id

    rule = AutomationRule.objects.create(
        board=board,
        name=name,
        description=description,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        is_active=True,
        created_by=request.user,
    )

    # Create actions
    action_types = request.POST.getlist("action_type")
    for i, action_type in enumerate(action_types):
        if action_type not in dict(AutomationAction.ActionType.choices):
            continue

        action_config = {}

        # Parse action-specific config
        if action_type == AutomationAction.ActionType.MOVE_CARD:
            col_id = (request.POST.get(f"action_column_id_{i}") or "").strip()
            if col_id:
                action_config["column_id"] = col_id
        elif action_type == AutomationAction.ActionType.ADD_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.REMOVE_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.SET_DUE_DATE:
            days = (request.POST.get(f"action_days_offset_{i}") or "3").strip()
            try:
                action_config["days_offset"] = int(days)
            except ValueError:
                action_config["days_offset"] = 3
        elif action_type == AutomationAction.ActionType.ASSIGN_USER:
            user_id = (request.POST.get(f"action_user_id_{i}") or "").strip()
            assign_triggered = request.POST.get(f"action_assign_triggered_{i}") == "on"
            if assign_triggered:
                action_config["assign_triggered_by"] = True
            elif user_id:
                action_config["user_id"] = user_id

        AutomationAction.objects.create(
            rule=rule,
            action_type=action_type,
            action_config=action_config,
            sort_order=i,
        )

    messages.success(request, _("Automation rule created"))
    return redirect("web:board_automations", board_id=board.id)


@login_required
def board_automation_rule_toggle(request, rule_id):
    """Toggle an automation rule on/off."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    rule = (
        AutomationRule.objects.select_related("board")
        .filter(
            id=rule_id,
            board__organization=request.active_org,
        )
        .first()
    )
    if rule is None:
        raise Http404()

    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active"])

    return redirect("web:board_automations", board_id=rule.board_id)


@login_required
def board_automation_rule_delete(request, rule_id):
    """Delete an automation rule."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    rule = (
        AutomationRule.objects.select_related("board")
        .filter(
            id=rule_id,
            board__organization=request.active_org,
        )
        .first()
    )
    if rule is None:
        raise Http404()

    board_id = rule.board_id
    rule.delete()

    messages.success(request, _("Automation rule deleted"))
    return redirect("web:board_automations", board_id=board_id)


@login_required
def board_card_button_create(request, board_id):
    """Create a new card button."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    name = (request.POST.get("name") or "").strip()
    icon = (request.POST.get("icon") or "play").strip()
    color = (request.POST.get("color") or "indigo").strip()
    show_when_has_label_id = (request.POST.get("show_when_has_label") or "").strip()
    hide_when_has_label_id = (request.POST.get("hide_when_has_label") or "").strip()

    if not name:
        return HttpResponse("", status=400)

    button = CardButton.objects.create(
        board=board,
        name=name,
        icon=icon,
        color=color,
        is_active=True,
        created_by=request.user,
    )

    # Set label display conditions
    if show_when_has_label_id:
        button.show_when_has_label_id = show_when_has_label_id
    if hide_when_has_label_id:
        button.hide_when_has_label_id = hide_when_has_label_id
    if show_when_has_label_id or hide_when_has_label_id:
        button.save()

    # Create actions
    action_types = request.POST.getlist("action_type")
    for i, action_type in enumerate(action_types):
        if action_type not in dict(AutomationAction.ActionType.choices):
            continue

        action_config = {}

        if action_type == AutomationAction.ActionType.MOVE_CARD:
            col_id = (request.POST.get(f"action_column_id_{i}") or "").strip()
            if col_id:
                action_config["column_id"] = col_id
        elif action_type == AutomationAction.ActionType.ADD_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.REMOVE_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.SET_DUE_DATE:
            days = (request.POST.get(f"action_days_offset_{i}") or "3").strip()
            try:
                action_config["days_offset"] = int(days)
            except ValueError:
                action_config["days_offset"] = 3

        CardButtonAction.objects.create(
            button=button,
            action_type=action_type,
            action_config=action_config,
            sort_order=i,
        )

    messages.success(request, _("Card button created"))
    return redirect("web:board_automations", board_id=board.id)


@login_required
def board_card_button_delete(request, button_id):
    """Delete a card button."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    button = (
        CardButton.objects.select_related("board")
        .filter(
            id=button_id,
            board__organization=request.active_org,
        )
        .first()
    )
    if button is None:
        raise Http404()

    board_id = button.board_id
    button.delete()

    messages.success(request, _("Card button deleted"))
    return redirect("web:board_automations", board_id=board_id)


@login_required
def board_card_button_execute(request, card_id, button_id):
    """Execute a card button on a specific card."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(
            id=card_id,
            column__board__organization=request.active_org,
        )
        .first()
    )
    if card is None:
        raise Http404()

    button = CardButton.objects.filter(
        id=button_id,
        board=card.column.board,
        is_active=True,
    ).first()
    if button is None:
        raise Http404()

    success = execute_card_button(str(button.id), card, request.user)

    if success:
        messages.success(request, _("Button action executed"))
    else:
        messages.error(request, _("Button action failed"))

    return redirect("web:board_card_detail", card_id=card.id)


@login_required
def board_label_create(request, board_id):
    """Create a new label for a board."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    name = (request.POST.get("name") or "").strip()
    color = (request.POST.get("color") or "gray").strip()

    if not name:
        return HttpResponse("", status=400)

    BoardCardLabel.objects.get_or_create(
        board=board,
        name=name,
        defaults={"color": color},
    )

    return redirect("web:board_automations", board_id=board.id)


def _get_org_member_user(org, user_id_raw: str):
    user_id_raw = (user_id_raw or "").strip()
    if not user_id_raw:
        return None
    if not Membership.objects.filter(organization=org, user_id=user_id_raw).exists():
        return None
    User = get_user_model()
    return User.objects.filter(id=user_id_raw, is_active=True).first()


@login_required
def team_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )
    member_user_ids = list(members.values_list("user_id", flat=True))

    User = get_user_model()
    available_users = (
        User.objects.exclude(id__in=member_user_ids)
        .filter(is_active=True)
        .filter(Q(email__isnull=False) & ~Q(email=""))
        .order_by("email")
    )
    invitations = OrganizationInvitation.objects.filter(
        organization=org, status=OrganizationInvitation.Status.PENDING
    ).order_by("-created_at")

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
    if role not in {
        Membership.Role.ADMIN,
        Membership.Role.MEMBER,
        Membership.Role.OWNER,
    }:
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

    invite_url = (
        f"{request.scheme}://{request.get_host()}/app/invite/{invitation.token}/"
    )

    if existing_user is None:
        request.session["last_invite_url"] = invite_url
        send_mail(
            subject=f"Invitation to join {org.name}",
            message=(
                f"You have been invited to join {org.name}.\n\n"
                f"Accept the invitation here:\n{invite_url}\n\n"
                f"This invitation expires on {invitation.expires_at:%Y-%m-%d}."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or "no-reply@localhost",
            recipient_list=[email],
            fail_silently=False,
        )

    return redirect("web:team")


@login_required
def invite_accept(request, token):
    try:
        invitation = OrganizationInvitation.objects.select_related("organization").get(
            token=token
        )
    except OrganizationInvitation.DoesNotExist as exc:
        raise Http404() from exc

    if invitation.status != OrganizationInvitation.Status.PENDING:
        raise Http404()
    if invitation.is_expired():
        OrganizationInvitation.objects.filter(id=invitation.id).update(
            status=OrganizationInvitation.Status.EXPIRED
        )
        raise Http404()

    if request.method == "GET":
        context = {
            "org": invitation.organization,
            "orgs": Organization.objects.filter(
                memberships__user=request.user
            ).distinct(),
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

    if status not in {
        Project.Status.PLANNED,
        Project.Status.ACTIVE,
        Project.Status.COMPLETED,
        Project.Status.CANCELLED,
    }:
        return HttpResponse("", status=400)
    if category not in {c for c, _ in Project.Category.choices}:
        return HttpResponse("", status=400)
    if priority not in {
        Project.Priority.LOW,
        Project.Priority.MEDIUM,
        Project.Priority.HIGH,
    }:
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
        return render(
            request, "web/app/projects/_project_row.html", {"project": project}
        )

    return redirect("web:projects")


@login_required
def projects_complete(request, project_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    membership = (
        Membership.objects.filter(organization=request.active_org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role != Membership.Role.OWNER:
        return HttpResponseForbidden("")

    project = Project.objects.filter(
        id=project_id, organization=request.active_org
    ).first()
    if project is None:
        raise Http404()

    if project.status != Project.Status.COMPLETED:
        Project.objects.filter(id=project.id).update(status=Project.Status.COMPLETED)
        project.status = Project.Status.COMPLETED

    if request.headers.get("HX-Request") == "true":
        return render(
            request, "web/app/projects/_project_row.html", {"project": project}
        )

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
        Task.objects.filter(
            project=project, scheduled_start__isnull=True, is_archived=False
        )
        .select_related("assigned_to")
        .order_by("status", "sort_order", "-created_at")
    )
    in_progress_unscheduled = (
        Task.objects.filter(
            project=project,
            scheduled_start__isnull=True,
            status=Task.Status.IN_PROGRESS,
            is_archived=False,
        )
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

    qs = Task.objects.filter(
        project=project, scheduled_start__isnull=False, is_archived=False
    )

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
    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )
    open_started_at_subquery = Subquery(
        TaskTimeEntry.objects.filter(
            task_id=OuterRef("pk"), user=request.user, stopped_at__isnull=True
        )
        .order_by("-started_at")
        .values("started_at")[:1]
    )

    tasks = (
        Task.objects.filter(project__organization=org, is_archived=False)
        .select_related("project", "assigned_to", "idea_card")
        .prefetch_related("links", "label_assignments__label")
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

    todo_tasks = list(
        tasks.filter(status=Task.Status.TODO).order_by("sort_order", "-created_at")
    )
    in_progress_tasks = list(
        tasks.filter(status=Task.Status.IN_PROGRESS).order_by(
            "sort_order", "-created_at"
        )
    )
    done_tasks = list(
        tasks.filter(status=Task.Status.DONE).order_by("sort_order", "-created_at")
    )

    running_task_ids = list(
        tasks.filter(running_started_at__isnull=False).values_list("id", flat=True)
    )

    done_total_seconds = sum(task.tracked_seconds or 0 for task in done_tasks)
    done_total_human = _humanize_seconds(done_total_seconds)

    project_time_overview = []
    active_project_total_seconds = 0
    active_project_total_human = _humanize_seconds(0)
    active_project_top_tasks = []

    if active_project is not None:
        active_project_total_seconds = int(
            Task.objects.filter(project=active_project, is_archived=False)
            .aggregate(total=Sum("tracked_seconds"))
            .get("total")
            or 0
        )
        active_project_total_human = _humanize_seconds(active_project_total_seconds)
        active_project_top_tasks = list(
            Task.objects.filter(project=active_project, is_archived=False)
            .exclude(tracked_seconds=0)
            .order_by("-tracked_seconds")[:5]
        )
    else:
        rows = (
            Task.objects.filter(project__organization=org, is_archived=False)
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

    # Load all buttons for the organization/project
    all_buttons = list(
        TaskButton.objects.filter(organization=org, is_active=True)
        .filter(models.Q(project=active_project) | models.Q(project__isnull=True))
        .prefetch_related("actions", "show_when_has_label", "hide_when_has_label")
        if active_project
        else TaskButton.objects.filter(
            organization=org, is_active=True, project__isnull=True
        ).prefetch_related("actions", "show_when_has_label", "hide_when_has_label")
    )

    # Attach filtered buttons to each task
    for task in todo_tasks + in_progress_tasks + done_tasks:
        task.filtered_buttons = [
            btn for btn in all_buttons if btn.should_show_for_task(task)
        ]

    context = {
        **_web_shell_context(request),
        "projects": projects,
        "idea_cards": BoardCard.objects.filter(column__board__organization=org)
        .select_related("column__board")
        .order_by("column__board__title", "title"),
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
    qs = Task.objects.filter(
        project__organization=org, status=status, is_archived=False
    ).order_by("sort_order", "-created_at")
    for idx, task in enumerate(qs):
        if task.sort_order != idx:
            Task.objects.filter(id=task.id).update(sort_order=idx)


def _insert_task_at_position(org, task: Task, new_status: str, position: int):
    ids = list(
        Task.objects.filter(
            project__organization=org, status=new_status, is_archived=False
        )
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
    due_date_raw = (request.POST.get("due_date") or "").strip()
    idea_card_id = (request.POST.get("idea_card_id") or "").strip()
    link_url = (request.POST.get("link_url") or "").strip()
    link_title = (request.POST.get("link_title") or "").strip()

    if not title:
        return JsonResponse(
            {"error": _("Bitte geben Sie einen Titel für die Aufgabe ein.")}, status=400
        )

    if not project_id:
        return JsonResponse(
            {"error": _("Bitte wählen Sie ein Projekt aus.")}, status=400
        )

    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist:
        return JsonResponse(
            {"error": _("Das ausgewählte Projekt wurde nicht gefunden.")}, status=400
        )

    assigned_to = request.user
    if assigned_to_id:
        if not Membership.objects.filter(
            organization=org, user_id=assigned_to_id
        ).exists():
            return JsonResponse(
                {
                    "error": _(
                        "Der ausgewählte Benutzer ist kein Mitglied dieser Organisation."
                    )
                },
                status=400,
            )
        assigned_to = Membership.objects.get(
            organization=org, user_id=assigned_to_id
        ).user

    due_date = None
    if due_date_raw:
        due_d = parse_date(due_date_raw)
        if due_d is None:
            return JsonResponse(
                {"error": _("Das Fälligkeitsdatum hat ein ungültiges Format.")},
                status=400,
            )

        due_date = datetime.combine(due_d, time(17, 0))
        if timezone.is_naive(due_date):
            due_date = timezone.make_aware(due_date)

        if due_date < project.start_date or due_date > project.end_date:
            project_start = project.start_date.strftime("%d.%m.%Y")
            project_end = project.end_date.strftime("%d.%m.%Y")
            return JsonResponse(
                {
                    "error": _(
                        "Das Fälligkeitsdatum muss innerhalb des Projektzeitraums liegen ({start} - {end})."
                    ).format(start=project_start, end=project_end)
                },
                status=400,
            )

    idea_card = None
    if idea_card_id:
        idea_card = BoardCard.objects.filter(
            id=idea_card_id,
            column__board__organization=org,
        ).first()
        if idea_card is None:
            return JsonResponse(
                {"error": _("Die ausgewählte Ideen-Karte wurde nicht gefunden.")},
                status=400,
            )

    task = Task.objects.create(
        project=project,
        title=title,
        assigned_to=assigned_to,
        status=Task.Status.TODO,
        due_date=due_date,
        idea_card=idea_card,
    )

    if link_url:
        TaskLink.objects.create(task=task, url=link_url, title=link_title)

    if task.assigned_to_id != request.user.id:
        Task.objects.filter(id=task.id).update(sort_order=0)

    _normalize_column_order(org, Task.Status.TODO)

    # Trigger task automation
    engine = TaskAutomationEngine(triggered_by=request.user)
    engine.trigger_task_created(task)

    if request.headers.get("HX-Request") == "true":
        members = (
            Membership.objects.filter(organization=org)
            .select_related("user")
            .order_by("user__email")
        )
        task = (
            Task.objects.select_related("project", "assigned_to", "idea_card")
            .prefetch_related("links")
            .get(id=task.id)
        )
        oob_target = {
            Task.Status.TODO: "col-todo",
            Task.Status.IN_PROGRESS: "col-inprogress",
            Task.Status.DONE: "col-done",
        }.get(task.status, "col-todo")

        response = render(
            request,
            "web/app/tasks/_task_card.html",
            {
                "task": task,
                "members": members,
                "running_task_ids": [],
                "hx_swap_oob_target": oob_target,
            },
        )
        response.headers["HX-Trigger"] = json.dumps(
            {"taskCreated": {"task_id": str(task.id)}}
        )
        return response

    return redirect("web:tasks")


@login_required
def tasks_detail(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None:
        raise Http404()

    try:
        task = (
            Task.objects.select_related("project", "assigned_to", "idea_card")
            .prefetch_related("links")
            .get(id=task_id, project__organization=org)
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    can_edit = _can_edit_task(request, task)

    if request.method == "POST":
        permission_response = _require_task_edit_permission(request, task)
        if permission_response is not None:
            return permission_response

        title = (request.POST.get("title") or "").strip()
        subtitle = (request.POST.get("subtitle") or "").strip()
        description = (request.POST.get("description") or "").strip()
        status = (request.POST.get("status") or "").strip().upper()
        priority = (request.POST.get("priority") or "").strip().upper()
        assigned_to_id = (request.POST.get("assigned_to") or "").strip()
        due_date_raw = (request.POST.get("due_date") or "").strip()

        if not title:
            return HttpResponse("", status=400)

        if status and status not in {
            Task.Status.TODO,
            Task.Status.IN_PROGRESS,
            Task.Status.DONE,
        }:
            return HttpResponse("", status=400)
        if priority and priority not in {
            Task.Priority.LOW,
            Task.Priority.MEDIUM,
            Task.Priority.HIGH,
        }:
            return HttpResponse("", status=400)

        assigned_to = task.assigned_to
        if assigned_to_id:
            if not Membership.objects.filter(
                organization=org, user_id=assigned_to_id
            ).exists():
                return HttpResponse("", status=400)
            assigned_to = Membership.objects.get(
                organization=org, user_id=assigned_to_id
            ).user

        due_date = None
        if due_date_raw:
            due_d = parse_date(due_date_raw)
            if due_d is None:
                return HttpResponse("", status=400)

            due_date = datetime.combine(due_d, time(17, 0))
            if timezone.is_naive(due_date):
                due_date = timezone.make_aware(due_date)

            if due_date < task.project.start_date or due_date > task.project.end_date:
                return HttpResponse("", status=400)

        update_fields = {
            "title": title,
            "subtitle": subtitle,
            "description": description or None,
            "assigned_to": assigned_to,
            "due_date": due_date,
        }
        if status:
            update_fields["status"] = status
        if priority:
            update_fields["priority"] = priority

        Task.objects.filter(id=task.id).update(**update_fields)
        return redirect("web:tasks_detail", task_id=task.id)

    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )
    context = {
        **_web_shell_context(request),
        "task": task,
        "members": members,
        "can_edit": can_edit,
    }
    return render(request, "web/app/tasks/detail.html", context)


@login_required
def tasks_delete(request, task_id):
    """Archive a task (soft delete)."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org, is_archived=False
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    # Archive instead of delete
    Task.objects.filter(id=task.id).update(
        is_archived=True,
        archived_at=timezone.now(),
        archived_by=request.user,
    )

    messages.success(request, _("Task archived"))
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
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org
        )
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
        task = Task.objects.select_related("project", "assigned_to").get(
            id=task_id, project__organization=org
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    assigned_to_id = (request.POST.get("assigned_to") or "").strip()
    assigned_to = request.user
    if assigned_to_id:
        if not Membership.objects.filter(
            organization=org, user_id=assigned_to_id
        ).exists():
            return HttpResponse("", status=400)
        assigned_to = Membership.objects.get(
            organization=org, user_id=assigned_to_id
        ).user

    if task.assigned_to_id != assigned_to.id:
        Task.objects.filter(id=task.id).update(assigned_to=assigned_to)
        task.assigned_to = assigned_to

    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )
    if request.headers.get("HX-Request") == "true":
        started_at = (
            TaskTimeEntry.objects.filter(
                task_id=task.id, user=request.user, stopped_at__isnull=True
            )
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
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org
        )
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
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    clear_due = (request.POST.get("clear_due_date") or "").strip() in {
        "1",
        "true",
        "yes",
    }

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
        task = Task.objects.select_related("project", "assigned_to").get(
            id=task_id, project__organization=org
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    if request.method == "GET":
        mode = (request.GET.get("mode") or "view").strip().lower()
        if mode == "edit":
            return render(
                request, "web/app/tasks/_task_title_edit.html", {"task": task}
            )
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
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org
        )
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

    # Trigger task automation for status change
    if old_status != new_status:
        engine = TaskAutomationEngine(triggered_by=request.user)
        engine.trigger_status_changed(task, old_status, new_status)

        # Trigger task completed if status is DONE
        if new_status == Task.Status.DONE:
            engine.trigger_task_completed(task)

    # Refresh task to get updated labels and data from automation
    task.refresh_from_db()
    task = (
        Task.objects.filter(id=task.id)
        .select_related("project", "assigned_to", "idea_card")
        .prefetch_related("links", "label_assignments__label")
        .first()
    )

    # Load buttons for this task
    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )
    all_buttons = list(
        TaskButton.objects.filter(organization=org, is_active=True)
        .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
        .prefetch_related("actions", "show_when_has_label", "hide_when_has_label")
    )
    task.filtered_buttons = [
        btn for btn in all_buttons if btn.should_show_for_task(task)
    ]

    # Check if task is running
    started_at = (
        TaskTimeEntry.objects.filter(
            task_id=task.id, user=request.user, stopped_at__isnull=True
        )
        .order_by("-started_at")
        .values_list("started_at", flat=True)
        .first()
    )
    running_task_ids = [task.id] if started_at else []
    task.running_started_at = started_at

    # Return updated card HTML
    return render(
        request,
        "web/app/tasks/_task_card.html",
        {"task": task, "members": members, "running_task_ids": running_task_ids},
    )


@login_required
def tasks_toggle(request, task_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    old_status = task.status
    new_status = (
        Task.Status.DONE if task.status != Task.Status.DONE else Task.Status.TODO
    )

    with transaction.atomic():
        task.status = new_status
        task.save(update_fields=["status", "updated_at"])

        # Trigger task automation for status change
        engine = TaskAutomationEngine(triggered_by=request.user)
        engine.trigger_status_changed(task, old_status, new_status)

        if new_status == Task.Status.DONE:
            engine.trigger_task_completed(task)

        if new_status == Task.Status.DONE:
            now = timezone.now()
            open_entries = list(
                TaskTimeEntry.objects.filter(task=task, stopped_at__isnull=True)
            )
            total_added = 0
            for entry in open_entries:
                delta = now - entry.started_at
                added = max(0, int(delta.total_seconds()))
                if added:
                    TaskTimeEntry.objects.filter(id=entry.id).update(
                        stopped_at=now, duration_seconds=entry.duration_seconds + added
                    )
                    total_added += added
                else:
                    TaskTimeEntry.objects.filter(id=entry.id).update(stopped_at=now)

            if total_added:
                Task.objects.filter(id=task.id).update(
                    tracked_seconds=F("tracked_seconds") + total_added
                )

        _normalize_column_order(org, new_status)
        if old_status != new_status:
            _normalize_column_order(org, old_status)

    if request.headers.get("HX-Request") == "true":
        members = (
            Membership.objects.filter(organization=org)
            .select_related("user")
            .order_by("user__email")
        )
        task.refresh_from_db(fields=["tracked_seconds"])
        started_at = (
            TaskTimeEntry.objects.filter(
                task_id=task.id, user=request.user, stopped_at__isnull=True
            )
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
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    now = timezone.now()
    open_entry = (
        TaskTimeEntry.objects.filter(
            task=task, user=request.user, stopped_at__isnull=True
        )
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
            Task.objects.filter(id=task.id).update(
                tracked_seconds=F("tracked_seconds") + added
            )
            task.refresh_from_db(fields=["tracked_seconds"])

    if request.headers.get("HX-Request") == "true":
        members = (
            Membership.objects.filter(organization=org)
            .select_related("user")
            .order_by("user__email")
        )
        started_at = (
            TaskTimeEntry.objects.filter(
                task_id=task.id, user=request.user, stopped_at__isnull=True
            )
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
        Membership.objects.create(
            organization=org, user=request.user, role=Membership.Role.OWNER
        )
        request.session["active_org_id"] = str(org.id)

        return redirect("web:home")

    return render(request, "web/app/onboarding.html")


@login_required
def workspaces_new(request):
    if request.method == "GET":
        return render(
            request, "web/app/workspaces/new.html", {**_web_shell_context(request)}
        )

    if request.method != "POST":
        raise Http404()

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, _("Please provide a workspace name"))
        return render(
            request, "web/app/workspaces/new.html", {**_web_shell_context(request)}
        )

    base_slug = slugify(name) or "workspace"
    slug = base_slug
    idx = 1
    while Organization.objects.filter(slug=slug).exists():
        idx += 1
        slug = f"{base_slug}-{idx}"

    org = Organization.objects.create(name=name, slug=slug)
    Membership.objects.create(
        organization=org, user=request.user, role=Membership.Role.OWNER
    )
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


# ============================================================================
# Task Automation Management
# ============================================================================


@login_required
def task_automations(request):
    """Task automation management page."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None:
        raise Http404()

    # Get all automation rules for this organization
    rules = (
        TaskAutomationRule.objects.filter(organization=org)
        .select_related("project", "created_by")
        .prefetch_related("actions")
        .order_by("-created_at")
    )

    # Get all task buttons for this organization
    buttons = (
        TaskButton.objects.filter(organization=org)
        .select_related("project", "created_by")
        .prefetch_related("actions")
        .order_by("name")
    )

    # Get all labels for this organization
    labels = TaskLabel.objects.filter(organization=org).order_by("name")

    # Get all projects for dropdowns
    projects = Project.objects.filter(organization=org).order_by("title")

    # Get organization members for user assignment
    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )

    context = {
        **_web_shell_context(request),
        "rules": rules,
        "buttons": buttons,
        "labels": labels,
        "projects": projects,
        "members": members,
        "trigger_choices": TaskAutomationRule.TriggerType.choices,
        "action_choices": TaskAutomationAction.ActionType.choices,
        "status_choices": Task.Status.choices,
        "priority_choices": Task.Priority.choices,
    }

    return render(request, "web/app/tasks/automations.html", context)


@login_required
def task_automation_rule_create(request):
    """Create a new task automation rule."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        return HttpResponseForbidden()

    name = (request.POST.get("name") or "").strip()
    trigger_type = (request.POST.get("trigger_type") or "").strip()
    action_type = (request.POST.get("action_type") or "").strip()
    project_id = (request.POST.get("project_id") or "").strip()

    if not name or not trigger_type or not action_type:
        messages.error(request, _("Please fill all required fields"))
        return redirect("web:task_automations")

    # Build trigger config
    trigger_config = {}
    if trigger_type == TaskAutomationRule.TriggerType.STATUS_CHANGED:
        to_status = request.POST.get("to_status")
        if to_status:
            trigger_config["to_status"] = to_status
    elif trigger_type == TaskAutomationRule.TriggerType.PRIORITY_CHANGED:
        to_priority = request.POST.get("to_priority")
        if to_priority:
            trigger_config["to_priority"] = to_priority
    elif trigger_type in [
        TaskAutomationRule.TriggerType.LABEL_ADDED,
        TaskAutomationRule.TriggerType.LABEL_REMOVED,
    ]:
        trigger_label_id = request.POST.get("trigger_label_id")
        if trigger_label_id:
            trigger_config["label_id"] = trigger_label_id

    # Build action config
    action_config = {}
    if action_type == TaskAutomationAction.ActionType.CHANGE_STATUS:
        status = request.POST.get("action_status")
        if status:
            action_config["status"] = status
    elif action_type == TaskAutomationAction.ActionType.SET_PRIORITY:
        priority = request.POST.get("action_priority")
        if priority:
            action_config["priority"] = priority
    elif action_type == TaskAutomationAction.ActionType.ASSIGN_USER:
        assign_triggered_by = request.POST.get("assign_triggered_by") == "on"
        action_config["assign_triggered_by"] = assign_triggered_by
        if not assign_triggered_by:
            user_id = request.POST.get("user_id")
            if user_id:
                action_config["user_id"] = user_id
    elif action_type == TaskAutomationAction.ActionType.ADD_LABEL:
        label_id = request.POST.get("action_label_id")
        if label_id:
            action_config["label_id"] = label_id
    elif action_type == TaskAutomationAction.ActionType.REMOVE_LABEL:
        label_id = request.POST.get("action_label_id")
        if label_id:
            action_config["label_id"] = label_id
    elif action_type == TaskAutomationAction.ActionType.SET_DUE_DATE:
        days_offset = request.POST.get("days_offset", "3")
        try:
            action_config["days_offset"] = int(days_offset)
        except ValueError:
            action_config["days_offset"] = 3
    elif action_type == TaskAutomationAction.ActionType.MOVE_TO_PROJECT:
        target_project_id = request.POST.get("target_project_id")
        if target_project_id:
            action_config["project_id"] = target_project_id

    # Create rule
    project = None
    if project_id:
        project = Project.objects.filter(id=project_id, organization=org).first()

    rule = TaskAutomationRule.objects.create(
        organization=org,
        project=project,
        name=name,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        created_by=request.user,
    )

    # Create action
    TaskAutomationAction.objects.create(
        rule=rule,
        action_type=action_type,
        action_config=action_config,
        sort_order=0,
    )

    messages.success(request, _("Automation rule created"))
    return redirect("web:task_automations")


@login_required
def task_automation_rule_toggle(request, rule_id):
    """Toggle automation rule active status."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        return HttpResponseForbidden()

    try:
        rule = TaskAutomationRule.objects.get(id=rule_id, organization=org)
    except TaskAutomationRule.DoesNotExist as exc:
        raise Http404() from exc

    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active"])

    return redirect("web:task_automations")


@login_required
def task_automation_rule_delete(request, rule_id):
    """Delete an automation rule."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        return HttpResponseForbidden()

    try:
        rule = TaskAutomationRule.objects.get(id=rule_id, organization=org)
    except TaskAutomationRule.DoesNotExist as exc:
        raise Http404() from exc

    rule.delete()
    messages.success(request, _("Automation rule deleted"))
    return redirect("web:task_automations")


@login_required
def task_button_create(request):
    """Create a new task button."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        return HttpResponseForbidden()

    name = (request.POST.get("name") or "").strip()
    icon = (request.POST.get("icon") or "play").strip()
    color = (request.POST.get("color") or "indigo").strip()
    action_type = (request.POST.get("action_type") or "").strip()
    project_id = (request.POST.get("project_id") or "").strip()
    show_when_has_label_id = (request.POST.get("show_when_has_label") or "").strip()
    hide_when_has_label_id = (request.POST.get("hide_when_has_label") or "").strip()
    show_on_status = request.POST.getlist("show_on_status")
    show_on_priority = request.POST.getlist("show_on_priority")

    if not name or not action_type:
        messages.error(request, _("Please fill all required fields"))
        return redirect("web:task_automations")

    # Build action config (same as rule actions)
    action_config = {}
    if action_type == TaskAutomationAction.ActionType.CHANGE_STATUS:
        status = request.POST.get("action_status")
        if status:
            action_config["status"] = status
    elif action_type == TaskAutomationAction.ActionType.SET_PRIORITY:
        priority = request.POST.get("action_priority")
        if priority:
            action_config["priority"] = priority
    elif action_type == TaskAutomationAction.ActionType.ADD_LABEL:
        label_id = request.POST.get("label_id")
        if label_id:
            action_config["label_id"] = label_id
    elif action_type == TaskAutomationAction.ActionType.REMOVE_LABEL:
        label_id = request.POST.get("label_id")
        if label_id:
            action_config["label_id"] = label_id

    project = None
    if project_id:
        project = Project.objects.filter(id=project_id, organization=org).first()

    button = TaskButton.objects.create(
        organization=org,
        project=project,
        name=name,
        icon=icon,
        color=color,
        show_on_status=show_on_status if show_on_status else [],
        show_on_priority=show_on_priority if show_on_priority else [],
        created_by=request.user,
    )

    # Set label display conditions
    if show_when_has_label_id:
        button.show_when_has_label_id = show_when_has_label_id
    if hide_when_has_label_id:
        button.hide_when_has_label_id = hide_when_has_label_id
    if show_when_has_label_id or hide_when_has_label_id:
        button.save()

    TaskButtonAction.objects.create(
        button=button,
        action_type=action_type,
        action_config=action_config,
        sort_order=0,
    )

    messages.success(request, _("Task button created"))
    return redirect("web:task_automations")


@login_required
def task_button_delete(request, button_id):
    """Delete a task button."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        return HttpResponseForbidden()

    try:
        button = TaskButton.objects.get(id=button_id, organization=org)
    except TaskButton.DoesNotExist as exc:
        raise Http404() from exc

    button.delete()
    messages.success(request, _("Task button deleted"))
    return redirect("web:task_automations")


@login_required
def task_button_execute(request, task_id, button_id):
    """Execute a task button on a specific task."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org

    try:
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org, is_archived=False
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    success = execute_task_button(button_id, task, request.user)

    if not success:
        return JsonResponse({"error": _("Button action failed")}, status=400)

    # Reload task to get updated data
    task.refresh_from_db()

    # If task was archived, return empty response to remove it from the list
    if task.is_archived:
        return HttpResponse("")

    # Return updated task card for HTMX swap
    members = Membership.objects.filter(organization=org).select_related("user")

    open_started_at_subquery = Subquery(
        TaskTimeEntry.objects.filter(
            task_id=OuterRef("pk"), user=request.user, stopped_at__isnull=True
        )
        .order_by("-started_at")
        .values("started_at")[:1]
    )

    running_task_ids = list(
        Task.objects.filter(project__organization=org, is_archived=False)
        .annotate(running_started_at=open_started_at_subquery)
        .filter(running_started_at__isnull=False)
        .values_list("id", flat=True)
    )

    all_buttons = (
        TaskButton.objects.filter(organization=org, is_active=True)
        .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
        .prefetch_related("actions", "show_when_has_label", "hide_when_has_label")
    )

    # Filter buttons based on task conditions and attach to task
    task.filtered_buttons = [
        btn for btn in all_buttons if btn.should_show_for_task(task)
    ]

    return render(
        request,
        "web/app/tasks/_task_card.html",
        {
            "task": task,
            "members": members,
            "running_task_ids": running_task_ids,
        },
    )


@login_required
def task_label_create(request):
    """Create a new task label."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None:
        return HttpResponseForbidden()

    name = (request.POST.get("name") or "").strip()
    color = (request.POST.get("color") or "gray").strip()

    if not name:
        messages.error(request, _("Please provide a label name"))
        return redirect("web:task_automations")

    TaskLabel.objects.get_or_create(
        organization=org,
        name=name,
        defaults={"color": color},
    )

    messages.success(request, _("Label created"))
    return redirect("web:task_automations")


# ============================================================================
# Task Archive
# ============================================================================


@login_required
def tasks_archive(request):
    """View archived tasks."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    projects = Project.objects.filter(organization=org).order_by("title")

    # Get archived tasks
    archived_tasks = (
        Task.objects.filter(project__organization=org, is_archived=True)
        .select_related("project", "assigned_to", "archived_by")
        .order_by("-archived_at")
    )

    # Filter by project if specified
    project_id = (request.GET.get("project") or "").strip()
    active_project = None
    if project_id:
        try:
            active_project = Project.objects.get(id=project_id, organization=org)
            archived_tasks = archived_tasks.filter(project=active_project)
        except Project.DoesNotExist:
            pass

    context = {
        **_web_shell_context(request),
        "archived_tasks": archived_tasks,
        "projects": projects,
        "active_project": active_project,
    }
    return render(request, "web/app/tasks/archive.html", context)


@login_required
def tasks_restore(request, task_id):
    """Restore an archived task."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    try:
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org, is_archived=True
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    permission_response = _require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    # Restore task
    Task.objects.filter(id=task.id).update(
        is_archived=False,
        archived_at=None,
        archived_by=None,
    )

    messages.success(request, _("Task restored"))
    return redirect("web:tasks_archive")


@login_required
def tasks_delete_permanent(request, task_id):
    """Permanently delete an archived task."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user)
        .only("role")
        .first()
    )
    if membership is None or membership.role not in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }:
        return HttpResponseForbidden()

    try:
        task = Task.objects.select_related("project").get(
            id=task_id, project__organization=org, is_archived=True
        )
    except Task.DoesNotExist as exc:
        raise Http404() from exc

    task_title = task.title
    task.delete()

    messages.success(
        request, _("Task permanently deleted: %(title)s") % {"title": task_title}
    )
    return redirect("web:tasks_archive")
