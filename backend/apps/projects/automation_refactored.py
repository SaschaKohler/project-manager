"""
Task automation engine - Refactored version.

Uses BaseAutomationEngine and Action Registry Pattern for cleaner code.
"""

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

from apps.core.automation_base import BaseAutomationEngine, TriggerFilter
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


class TaskAutomationEngine(BaseAutomationEngine[Task]):
    """
    Automation engine for tasks using Action Registry Pattern.

    Cleaner implementation with:
    - Action registry instead of long if-elif chains
    - TriggerFilter for consistent trigger logic
    - Inherited base functionality from BaseAutomationEngine
    """

    def _build_action_registry(self) -> dict:
        """Build mapping of action types to handler methods."""
        return {
            TaskAutomationAction.ActionType.CHANGE_STATUS: self._action_change_status,
            TaskAutomationAction.ActionType.SET_PRIORITY: self._action_set_priority,
            TaskAutomationAction.ActionType.ASSIGN_USER: self._action_assign_user,
            TaskAutomationAction.ActionType.UNASSIGN_USER: self._action_unassign_user,
            TaskAutomationAction.ActionType.ADD_LABEL: self._action_add_label,
            TaskAutomationAction.ActionType.REMOVE_LABEL: self._action_remove_label,
            TaskAutomationAction.ActionType.SET_DUE_DATE: self._action_set_due_date,
            TaskAutomationAction.ActionType.CLEAR_DUE_DATE: self._action_clear_due_date,
            TaskAutomationAction.ActionType.MOVE_TO_PROJECT: self._action_move_to_project,
            TaskAutomationAction.ActionType.SEND_NOTIFICATION: self._action_send_notification,
            TaskAutomationAction.ActionType.POST_COMMENT: self._action_post_comment,
            TaskAutomationAction.ActionType.ADD_TO_CALENDAR: self._action_add_to_calendar,
            TaskAutomationAction.ActionType.ARCHIVE_TASK: self._action_archive_task,
        }

    # ========================================================================
    # Trigger Methods
    # ========================================================================

    def trigger_task_created(self, task: Task) -> list[TaskAutomationLog]:
        """Trigger automation when a task is created."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.TASK_CREATED)
        return self._execute_rules(rules, task)

    def trigger_status_changed(
        self, task: Task, old_status: str, new_status: str
    ) -> list[TaskAutomationLog]:
        """Trigger automation when task status changes."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.STATUS_CHANGED)
        filtered_rules = [
            rule
            for rule in rules
            if TriggerFilter.status_matches(rule, old_status, new_status)
        ]
        return self._execute_rules(filtered_rules, task)

    def trigger_task_updated(self, task: Task) -> list[TaskAutomationLog]:
        """Trigger automation when task is updated."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.TASK_UPDATED)
        return self._execute_rules(rules, task)

    def trigger_task_completed(self, task: Task) -> list[TaskAutomationLog]:
        """Trigger automation when task is completed."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.TASK_COMPLETED)
        return self._execute_rules(rules, task)

    def trigger_label_added(
        self, task: Task, label: TaskLabel
    ) -> list[TaskAutomationLog]:
        """Trigger automation when a label is added to task."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.LABEL_ADDED)
        filtered_rules = [
            rule for rule in rules if TriggerFilter.label_matches(rule, label)
        ]
        return self._execute_rules(filtered_rules, task)

    def trigger_label_removed(
        self, task: Task, label: TaskLabel
    ) -> list[TaskAutomationLog]:
        """Trigger automation when a label is removed from task."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.LABEL_REMOVED)
        filtered_rules = [
            rule for rule in rules if TriggerFilter.label_matches(rule, label)
        ]
        return self._execute_rules(filtered_rules, task)

    def trigger_assigned_to_user(
        self, task: Task, user: "User"
    ) -> list[TaskAutomationLog]:
        """Trigger automation when task is assigned to a user."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.ASSIGNED_TO_USER)
        return self._execute_rules(rules, task)

    def trigger_priority_changed(
        self, task: Task, old_priority: str, new_priority: str
    ) -> list[TaskAutomationLog]:
        """Trigger automation when task priority changes."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.PRIORITY_CHANGED)
        filtered_rules = [
            rule
            for rule in rules
            if TriggerFilter.priority_matches(rule, old_priority, new_priority)
        ]
        return self._execute_rules(filtered_rules, task)

    def trigger_due_date_approaching(
        self, task: Task, days_until_due: int
    ) -> list[TaskAutomationLog]:
        """Trigger automation when due date is approaching."""
        rules = self._get_rules(
            task, TaskAutomationRule.TriggerType.DUE_DATE_APPROACHING
        )
        filtered_rules = [
            rule
            for rule in rules
            if TriggerFilter.days_threshold_matches(rule, days_until_due)
        ]
        return self._execute_rules(filtered_rules, task)

    def trigger_due_date_reached(self, task: Task) -> list[TaskAutomationLog]:
        """Trigger automation when due date is reached."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.DUE_DATE_REACHED)
        return self._execute_rules(rules, task)

    def trigger_due_date_overdue(
        self, task: Task, days_overdue: int
    ) -> list[TaskAutomationLog]:
        """Trigger automation when task is overdue."""
        rules = self._get_rules(task, TaskAutomationRule.TriggerType.DUE_DATE_OVERDUE)
        filtered_rules = [
            rule for rule in rules if TriggerFilter.interval_matches(rule, days_overdue)
        ]
        return self._execute_rules(filtered_rules, task)

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_rules(self, task: Task, trigger_type: str):
        """Get active automation rules for a task and trigger type."""
        return (
            TaskAutomationRule.objects.filter(
                organization=task.project.organization,
                trigger_type=trigger_type,
                is_active=True,
            )
            .filter(models.Q(project=task.project) | models.Q(project__isnull=True))
            .prefetch_related("actions")
        )

    def _execute_rule(self, rule: TaskAutomationRule, task: Task) -> TaskAutomationLog:
        """Execute all actions for a single rule."""
        try:
            with transaction.atomic():
                for action in rule.actions.all():
                    config = action.action_config or {}
                    self._execute_action(action, task, config)

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

    # ========================================================================
    # Action Handlers
    # ========================================================================

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

    def _action_unassign_user(self, task: Task, config: dict) -> None:
        """Unassign user from task (not implemented - requires nullable assigned_to)."""
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

    def _action_clear_due_date(self, task: Task, config: dict) -> None:
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

        if target_project:
            task.project = target_project
            task.save(update_fields=["project"])

    def _action_send_notification(self, task: Task, config: dict) -> None:
        """Send notification (placeholder for future implementation)."""
        logger.info(f"Notification action triggered for task {task.id}")

    def _action_post_comment(self, task: Task, config: dict) -> None:
        """Post a comment on the task (placeholder for future implementation)."""
        comment_text = config.get("comment", "")
        logger.info(f"Comment action triggered for task {task.id}: {comment_text}")

    def _action_add_to_calendar(self, task: Task, config: dict) -> None:
        """Add task to calendar."""
        if not task.scheduled_start:
            duration = config.get("duration_minutes", 60)
            task.scheduled_start = timezone.now()
            task.duration_minutes = int(duration)
            task.save(update_fields=["scheduled_start", "duration_minutes"])

    def _action_archive_task(self, task: Task, config: dict) -> None:
        """Archive the task."""
        task.is_archived = True
        task.archived_at = timezone.now()
        if self.triggered_by:
            task.archived_by = self.triggered_by
        task.save(update_fields=["is_archived", "archived_at", "archived_by"])


# ============================================================================
# Task Button Execution
# ============================================================================


def execute_task_button(task: Task, button, triggered_by: "User | None" = None):
    """
    Execute all actions associated with a task button.

    Args:
        task: Task to execute actions on
        button: TaskButton instance
        triggered_by: User who triggered the button
    """
    engine = TaskAutomationEngine(triggered_by=triggered_by)

    with transaction.atomic():
        for action in button.actions.all():
            config = action.action_config or {}
            engine._execute_action(action, task, config)
