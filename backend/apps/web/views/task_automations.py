import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import OuterRef, Subquery
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.projects.automation import execute_task_button
from apps.projects.models import (
    Project,
    Task,
    TaskAutomationAction,
    TaskAutomationRule,
    TaskButton,
    TaskButtonAction,
    TaskLabel,
    TaskTimeEntry,
)
from apps.tenants.models import Membership

from .utils import require_task_edit_permission, web_shell_context


@login_required
def task_automations(request):
    """Task automation management page."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    membership = (
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
    )
    if membership is None:
        raise Http404()

    rules = (
        TaskAutomationRule.objects.filter(organization=org)
        .select_related("project", "created_by")
        .prefetch_related("actions")
        .order_by("-created_at")
    )

    buttons = (
        TaskButton.objects.filter(organization=org)
        .select_related("project", "created_by")
        .prefetch_related("actions")
        .order_by("name")
    )

    labels = TaskLabel.objects.filter(organization=org).order_by("name")

    projects = Project.objects.filter(organization=org).order_by("title")

    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )

    context = {
        **web_shell_context(request),
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
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
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
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
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
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
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
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
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
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
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

    permission_response = require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response

    success = execute_task_button(button_id, task, request.user)

    if not success:
        return JsonResponse({"error": _("Button action failed")}, status=400)

    task.refresh_from_db()

    if task.is_archived:
        return HttpResponse("")

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

    task.filtered_buttons = [btn for btn in all_buttons if btn.should_show_for_task(task)]

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
        Membership.objects.filter(organization=org, user=request.user).only("role").first()
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
