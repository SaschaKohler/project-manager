from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    User = get_user_model()

from .models import (
    Task,
    TaskAutomationAction,
    TaskAutomationLog,
    TaskAutomationRule,
    TaskLabel,
    TaskLabelAssignment,
    Project,
)

logger = logging.getLogger(__name__)


class TaskAutomationEngine:
    def __init__(self, triggered_by: "User | None" = None):
        self.triggered_by = triggered_by

    def trigger_task_created(self, task: Task) -> list[TaskAutomationLog]:
        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        return self._execute_rules(rules, task)

    def trigger_status_changed(
        self,
        task: Task,
        old_status: str,
        new_status: str,
    ) -> list[TaskAutomationLog]:
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.STATUS_CHANGED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}

            # Check if rule has status filter
            target_status = config.get("to_status")
            source_status = config.get("from_status")

            # Skip if rule specifies a target status and it doesn't match
            if target_status and new_status != target_status:
                continue

            # Skip if rule specifies a source status and it doesn't match
            if source_status and old_status != source_status:
                continue

            log = self._execute_rule(rule, task)
            logs.append(log)

        return logs

    def trigger_task_updated(self, task: Task) -> list[TaskAutomationLog]:
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.TASK_UPDATED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        return self._execute_rules(rules, task)

    def trigger_task_completed(self, task: Task) -> list[TaskAutomationLog]:
        """Trigger automation rules when a task is completed."""
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.TASK_COMPLETED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        return self._execute_rules(rules, task)

    def trigger_label_added(
        self, task: Task, label: TaskLabel
    ) -> list[TaskAutomationLog]:
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.LABEL_ADDED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            target_label_id = config.get("label_id")

            # Skip if rule specifies a label and it doesn't match
            if target_label_id and str(label.id) != str(target_label_id):
                continue

            log = self._execute_rule(rule, task)
            logs.append(log)

        return logs

    def trigger_label_removed(
        self, task: Task, label: TaskLabel
    ) -> list[TaskAutomationLog]:
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.LABEL_REMOVED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            target_label_id = config.get("label_id")

            if target_label_id and str(label.id) != str(target_label_id):
                continue

            log = self._execute_rule(rule, task)
            logs.append(log)

        return logs

    def trigger_assigned_to_user(
        self, task: Task, user: "User"
    ) -> list[TaskAutomationLog]:
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.ASSIGNED_TO_USER,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            target_user_id = config.get("user_id")

            if target_user_id and str(user.id) != str(target_user_id):
                continue

            log = self._execute_rule(rule, task)
            logs.append(log)

        return logs

    def trigger_priority_changed(
        self,
        task: Task,
        old_priority: str,
        new_priority: str,
    ) -> list[TaskAutomationLog]:
        """Trigger automation rules when task priority changes."""
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.PRIORITY_CHANGED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            target_priority = config.get("to_priority")

            if target_priority and new_priority != target_priority:
                continue

            log = self._execute_rule(rule, task)
            logs.append(log)

        return logs

    def trigger_due_date_approaching(
        self, task: Task, days_until_due: int
    ) -> list[TaskAutomationLog]:
        """Trigger automation rules when due date is approaching."""
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.DUE_DATE_APPROACHING,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            threshold_days = config.get("days_before", 3)

            # Only trigger if days match the threshold
            if days_until_due == threshold_days:
                log = self._execute_rule(rule, task)
                logs.append(log)

        return logs

    def trigger_due_date_reached(self, task: Task) -> list[TaskAutomationLog]:
        """Trigger automation rules when due date is reached (today)."""
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.DUE_DATE_REACHED,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        return self._execute_rules(rules, task)

    def trigger_due_date_overdue(self, task: Task, days_overdue: int) -> list[TaskAutomationLog]:
        """Trigger automation rules when task is overdue."""
        from django.db import models

        rules = (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=TaskAutomationRule.TriggerType.DUE_DATE_OVERDUE,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            trigger_every_n_days = config.get("trigger_every_n_days", 1)

            # Only trigger on specific day intervals (e.g., every day, every 3 days)
            if days_overdue % trigger_every_n_days == 0:
                log = self._execute_rule(rule, task)
                logs.append(log)

        return logs

    def _execute_rules(self, rules, task: Task) -> list[TaskAutomationLog]:
        """Execute a queryset of rules for a task."""
        logs = []
        for rule in rules:
            log = self._execute_rule(rule, task)
            logs.append(log)
        return logs

    def _execute_rule(self, rule: TaskAutomationRule, task: Task) -> TaskAutomationLog:
        """Execute all actions for a single rule."""
        try:
            with transaction.atomic():
                for action in rule.actions.all():
                    self._execute_action(action, task)

            return TaskAutomationLog.objects.create(
                rule=rule,
                task=task,
                status=TaskAutomationLog.Status.SUCCESS,
                message=_("Rule executed successfully"),
            )
        except Exception as exc:
            logger.exception(
                "Task automation rule %s failed for task %s", rule.id, task.id
            )
            return TaskAutomationLog.objects.create(
                rule=rule,
                task=task,
                status=TaskAutomationLog.Status.FAILED,
                message=str(exc),
            )

    def _execute_action(self, action: TaskAutomationAction, task: Task) -> None:
        """Execute a single action on a task."""
        config = action.action_config or {}
        action_type = action.action_type

        if action_type == TaskAutomationAction.ActionType.CHANGE_STATUS:
            self._action_change_status(task, config)
        elif action_type == TaskAutomationAction.ActionType.SET_PRIORITY:
            self._action_set_priority(task, config)
        elif action_type == TaskAutomationAction.ActionType.ASSIGN_USER:
            self._action_assign_user(task, config)
        elif action_type == TaskAutomationAction.ActionType.UNASSIGN_USER:
            self._action_unassign_user(task)
        elif action_type == TaskAutomationAction.ActionType.ADD_LABEL:
            self._action_add_label(task, config)
        elif action_type == TaskAutomationAction.ActionType.REMOVE_LABEL:
            self._action_remove_label(task, config)
        elif action_type == TaskAutomationAction.ActionType.SET_DUE_DATE:
            self._action_set_due_date(task, config)
        elif action_type == TaskAutomationAction.ActionType.CLEAR_DUE_DATE:
            self._action_clear_due_date(task)
        elif action_type == TaskAutomationAction.ActionType.MOVE_TO_PROJECT:
            self._action_move_to_project(task, config)
        elif action_type == TaskAutomationAction.ActionType.SEND_NOTIFICATION:
            self._action_send_notification(task, config)
        elif action_type == TaskAutomationAction.ActionType.POST_COMMENT:
            self._action_post_comment(task, config)
        elif action_type == TaskAutomationAction.ActionType.ADD_TO_CALENDAR:
            self._action_add_to_calendar(task, config)
        elif action_type == TaskAutomationAction.ActionType.ARCHIVE_TASK:
            self._action_archive_task(task)

    def _action_change_status(self, task: Task, config: dict) -> None:
        """Change task status."""
        new_status = config.get("status")
        if not new_status or new_status not in dict(Task.Status.choices):
            return

        task.status = new_status
        task.save(update_fields=["status"])

    def _action_set_priority(self, task: Task, config: dict) -> None:
        """Set task priority."""
        new_priority = config.get("priority")
        if not new_priority or new_priority not in dict(Task.Priority.choices):
            return

        task.priority = new_priority
        task.save(update_fields=["priority"])

    def _action_assign_user(self, task: Task, config: dict) -> None:
        """Assign a user to the task."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        user_id = config.get("user_id")
        assign_triggered_by = config.get("assign_triggered_by", False)

        if assign_triggered_by and self.triggered_by:
            task.assigned_to = self.triggered_by
            task.save(update_fields=["assigned_to"])
        elif user_id:
            user = User.objects.filter(id=user_id, is_active=True).first()
            if user:
                task.assigned_to = user
                task.save(update_fields=["assigned_to"])

    def _action_unassign_user(self, task: Task) -> None:
        """Unassign user from the task."""
        # Task requires assigned_to, so we can't truly unassign
        # This would need a model change to make assigned_to nullable
        pass

    def _action_add_label(self, task: Task, config: dict) -> None:
        """Add a label to the task."""
        label_id = config.get("label_id")
        if not label_id:
            return

        label = TaskLabel.objects.filter(
            id=label_id,
            organization=task.project.organization,
        ).first()

        if label:
            TaskLabelAssignment.objects.get_or_create(task=task, label=label)

    def _action_remove_label(self, task: Task, config: dict) -> None:
        """Remove a label from the task."""
        label_id = config.get("label_id")
        if not label_id:
            return

        TaskLabelAssignment.objects.filter(task=task, label_id=label_id).delete()

    def _action_set_due_date(self, task: Task, config: dict) -> None:
        """Set due date on the task."""
        days_offset = config.get("days_offset", 3)
        task.due_date = timezone.now() + timedelta(days=int(days_offset))
        task.save(update_fields=["due_date"])

    def _action_clear_due_date(self, task: Task) -> None:
        """Clear due date from the task."""
        task.due_date = None
        task.save(update_fields=["due_date"])

    def _action_move_to_project(self, task: Task, config: dict) -> None:
        """Move task to a different project."""
        project_id = config.get("project_id")
        if not project_id:
            return

        target_project = Project.objects.filter(
            id=project_id,
            organization=task.project.organization,
        ).first()

        if target_project and target_project.id != task.project_id:
            task.project = target_project
            task.save(update_fields=["project"])

    def _action_send_notification(self, task: Task, config: dict) -> None:
        """Send a notification (placeholder for future implementation)."""
        # TODO: Implement notification system
        message = config.get("message", "")
        logger.info("Notification for task %s: %s", task.id, message)

    def _action_post_comment(self, task: Task, config: dict) -> None:
        """Post a comment on the task (placeholder for future implementation)."""
        # TODO: Implement comment system
        comment = config.get("comment", "")
        logger.info("Comment for task %s: %s", task.id, comment)

    def _action_add_to_calendar(self, task: Task, config: dict) -> None:
        """Add task to calendar (schedule it)."""
        if not task.scheduled_start:
            days_offset = config.get("days_offset", 1)
            task.scheduled_start = timezone.now() + timedelta(days=int(days_offset))

            # Set duration if specified
            duration = config.get("duration_minutes", 60)
            task.duration_minutes = int(duration)

            task.save(update_fields=["scheduled_start", "duration_minutes"])

    def _action_archive_task(self, task: Task) -> None:
        """Archive the task."""
        if not task.is_archived:
            task.is_archived = True
            task.archived_at = timezone.now()
            task.archived_by = self.triggered_by
            task.save(update_fields=["is_archived", "archived_at", "archived_by"])


def execute_task_button(button_id: str, task: Task, triggered_by: "User") -> bool:
    """Execute all actions for a task button."""
    from .models import TaskButton

    button = (
        TaskButton.objects.filter(id=button_id, is_active=True)
        .prefetch_related("actions")
        .first()
    )
    if not button:
        return False

    # Check if button is for this organization or project
    if button.organization_id != task.project.organization_id:
        return False

    if button.project_id and button.project_id != task.project_id:
        return False

    engine = TaskAutomationEngine(triggered_by=triggered_by)

    try:
        with transaction.atomic():
            for action in button.actions.all():
                # TaskButtonAction uses same action types as TaskAutomationAction
                fake_action = TaskAutomationAction(
                    action_type=action.action_type,
                    action_config=action.action_config,
                )
                engine._execute_action(fake_action, task)
        return True
    except Exception:
        logger.exception("Task button %s failed for task %s", button_id, task.id)
        return False
