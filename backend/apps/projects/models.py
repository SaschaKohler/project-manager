import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import Organization


class Project(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Category(models.TextChoices):
        WORKSHOP = "WORKSHOP", _("Workshop")
        RETREAT = "RETREAT", _("Retreat")
        CONSULTATION = "CONSULTATION", _("Consultation")
        IT_SERVICE = "IT_SERVICE", _("IT Service")
        MARKETING = "MARKETING", _("Marketing")
        DEVELOPMENT = "DEVELOPMENT", _("Development")
        DESIGN = "DESIGN", _("Design")
        RESEARCH = "RESEARCH", _("Research")
        SALES = "SALES", _("Sales")
        FINANCE = "FINANCE", _("Finance")
        LEGAL = "LEGAL", _("Legal")
        HR = "HR", _("HR")
        OPERATIONS = "OPERATIONS", _("Operations")
        EVENT = "EVENT", _("Event")
        CONTENT = "CONTENT", _("Content")
        TRAINING = "TRAINING", _("Training")

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.WORKSHOP
    )
    budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title

    @property
    def end_days_left(self) -> int:
        today = timezone.localdate()
        end_day = timezone.localtime(self.end_date).date()
        return (end_day - today).days


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "Todo"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        DONE = "DONE", "Done"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TODO
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    due_date = models.DateTimeField(blank=True, null=True)
    scheduled_start = models.DateTimeField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    idea_card = models.ForeignKey(
        "boards.BoardCard",
        on_delete=models.SET_NULL,
        related_name="tasks",
        blank=True,
        null=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tasks"
    )
    tracked_seconds = models.PositiveIntegerField(default=0)
    progress = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="archived_tasks",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "-created_at")

    def __str__(self) -> str:
        return self.title

    @property
    def tracked_human(self) -> str:
        seconds = int(self.tracked_seconds or 0)
        minutes = seconds // 60
        hours = minutes // 60
        minutes = minutes % 60
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"


class TaskTimeEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="time_entries"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_time_entries",
    )
    started_at = models.DateTimeField()
    stopped_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.task_id} · {self.user_id} · {self.started_at}"


class TaskLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="links")
    title = models.CharField(max_length=255, blank=True, default="")
    url = models.URLField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.url


class TaskLabel(models.Model):
    """Labels that can be attached to tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="task_labels")
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default="gray")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TaskLabelAssignment(models.Model):
    """M2M through model for task labels."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="label_assignments")
    label = models.ForeignKey(TaskLabel, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("task", "label")]


class TaskAutomationRule(models.Model):
    """Automation rules for tasks (like Trello Butler)."""

    class TriggerType(models.TextChoices):
        TASK_CREATED = "task_created", "Task Created"
        STATUS_CHANGED = "status_changed", "Status Changed"
        TASK_UPDATED = "task_updated", "Task Updated"
        DUE_DATE_APPROACHING = "due_date_approaching", "Due Date Approaching"
        DUE_DATE_REACHED = "due_date_reached", "Due Date Reached"
        DUE_DATE_OVERDUE = "due_date_overdue", "Due Date Overdue"
        LABEL_ADDED = "label_added", "Label Added"
        LABEL_REMOVED = "label_removed", "Label Removed"
        ASSIGNED_TO_USER = "assigned_to_user", "Assigned to User"
        PRIORITY_CHANGED = "priority_changed", "Priority Changed"
        TASK_COMPLETED = "task_completed", "Task Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="task_automation_rules")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="automation_rules", blank=True, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    trigger_type = models.CharField(max_length=32, choices=TriggerType.choices)
    trigger_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_task_automation_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_trigger_type_display()})"


class TaskAutomationAction(models.Model):
    """Actions to execute when a task automation rule triggers."""

    class ActionType(models.TextChoices):
        CHANGE_STATUS = "change_status", "Change Status"
        SET_PRIORITY = "set_priority", "Set Priority"
        ASSIGN_USER = "assign_user", "Assign User"
        UNASSIGN_USER = "unassign_user", "Unassign User"
        ADD_LABEL = "add_label", "Add Label"
        REMOVE_LABEL = "remove_label", "Remove Label"
        SET_DUE_DATE = "set_due_date", "Set Due Date"
        CLEAR_DUE_DATE = "clear_due_date", "Clear Due Date"
        MOVE_TO_PROJECT = "move_to_project", "Move to Project"
        SEND_NOTIFICATION = "send_notification", "Send Notification"
        POST_COMMENT = "post_comment", "Post Comment"
        ADD_TO_CALENDAR = "add_to_calendar", "Add to Calendar"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(TaskAutomationRule, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=32, choices=ActionType.choices)
    action_config = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return f"{self.get_action_type_display()}"


class TaskAutomationLog(models.Model):
    """Log of task automation executions for debugging and audit."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(TaskAutomationRule, on_delete=models.CASCADE, related_name="logs")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="automation_logs")
    status = models.CharField(max_length=16, choices=Status.choices)
    message = models.TextField(blank=True, default="")
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]


class TaskButton(models.Model):
    """Custom buttons that appear on tasks for one-click actions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="task_buttons")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="task_buttons", blank=True, null=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default="play")
    color = models.CharField(max_length=20, default="indigo")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_task_buttons",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TaskButtonAction(models.Model):
    """Actions to execute when a task button is clicked."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    button = models.ForeignKey(TaskButton, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=32, choices=TaskAutomationAction.ActionType.choices)
    action_config = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return f"{self.get_action_type_display()}"


class Event(models.Model):
    class Type(models.TextChoices):
        SESSION = "SESSION", "Session"
        MARKETING = "MARKETING", "Marketing"
        DEADLINE = "DEADLINE", "Deadline"
        MEETING = "MEETING", "Meeting"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="events"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.MEETING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title
