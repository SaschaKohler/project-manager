import uuid

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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

    class Color(models.TextChoices):
        INDIGO = "indigo", _("Indigo")
        EMERALD = "emerald", _("Emerald")
        SKY = "sky", _("Sky")
        VIOLET = "violet", _("Violet")
        ROSE = "rose", _("Rose")
        AMBER = "amber", _("Amber")
        TEAL = "teal", _("Teal")
        ORANGE = "orange", _("Orange")
        LIME = "lime", _("Lime")
        FUCHSIA = "fuchsia", _("Fuchsia")

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
    color = models.CharField(
        max_length=20, choices=Color.choices, default=Color.INDIGO
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_projects",
    )
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="archived_projects",
        blank=True,
        null=True,
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


class RecurrenceFrequency(models.TextChoices):
    DAILY = "DAILY", "Daily"
    WEEKLY = "WEEKLY", "Weekly"
    MONTHLY = "MONTHLY", "Monthly"


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
    recurrence_parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, blank=True, null=True, related_name='recurring_children'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "-created_at")

    def __str__(self) -> str:
        return self.title


class RecurringTask(models.Model):
    task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name='recurring')
    is_recurring = models.BooleanField(default=False)
    recurrence_frequency = models.CharField(
        max_length=20, choices=RecurrenceFrequency.choices, blank=True, null=True
    )
    recurrence_interval = models.PositiveIntegerField(default=1)
    recurrence_end_date = models.DateTimeField(blank=True, null=True)
    recurrence_max_occurrences = models.PositiveIntegerField(blank=True, null=True)
    recurrence_parent = models.ForeignKey(
        Task, on_delete=models.SET_NULL, blank=True, null=True, related_name='recurring_task_children'
    )

    def __str__(self) -> str:
        return f"Recurring settings for {self.task.title}"


@receiver(post_save, sender=Task)
def create_recurring_task(sender, instance, **kwargs):
    if instance.status == Task.Status.DONE and hasattr(instance, 'recurring') and instance.recurring.is_recurring:
        recurring = instance.recurring
        # Check termination conditions
        if recurring.recurrence_end_date and timezone.now() >= recurring.recurrence_end_date:
            return
        if recurring.recurrence_max_occurrences:
            child_count = Task.objects.filter(recurrence_parent=recurring.recurrence_parent or instance).count()
            if child_count >= recurring.recurrence_max_occurrences:
                return

        # Calculate next due date
        base_date = instance.due_date or instance.scheduled_start
        if not base_date:
            return

        interval = recurring.recurrence_interval
        if recurring.recurrence_frequency == RecurrenceFrequency.DAILY:
            next_date = base_date + relativedelta(days=interval)
        elif recurring.recurrence_frequency == RecurrenceFrequency.WEEKLY:
            next_date = base_date + relativedelta(weeks=interval)
        elif recurring.recurrence_frequency == RecurrenceFrequency.MONTHLY:
            next_date = base_date + relativedelta(months=interval)
        else:
            return

        # Create new task
        new_task = Task.objects.create(
            project=instance.project,
            title=instance.title,
            subtitle=instance.subtitle,
            description=instance.description,
            status=Task.Status.TODO,
            priority=instance.priority,
            due_date=next_date if instance.due_date else None,
            scheduled_start=next_date if instance.scheduled_start else None,
            duration_minutes=instance.duration_minutes,
            assigned_to=instance.assigned_to,
            progress=0,
        )
        # Create recurring settings for new task
        RecurringTask.objects.create(
            task=new_task,
            is_recurring=True,
            recurrence_frequency=recurring.recurrence_frequency,
            recurrence_interval=recurring.recurrence_interval,
            recurrence_end_date=recurring.recurrence_end_date,
            recurrence_max_occurrences=recurring.recurrence_max_occurrences,
            recurrence_parent=recurring.recurrence_parent or instance,
        )

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
        TASK_CREATED = "task_created", _("Task Created")
        STATUS_CHANGED = "status_changed", _("Status Changed")
        TASK_UPDATED = "task_updated", _("Task Updated")
        DUE_DATE_APPROACHING = "due_date_approaching", _("Due Date Approaching")
        DUE_DATE_REACHED = "due_date_reached", _("Due Date Reached")
        DUE_DATE_OVERDUE = "due_date_overdue", _("Due Date Overdue")
        LABEL_ADDED = "label_added", _("Label Added")
        LABEL_REMOVED = "label_removed", _("Label Removed")
        ASSIGNED_TO_USER = "assigned_to_user", _("Assigned to User")
        PRIORITY_CHANGED = "priority_changed", _("Priority Changed")
        TASK_COMPLETED = "task_completed", _("Task Completed")

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

    is_recurring = models.BooleanField(default=False)
    recurrence_frequency = models.CharField(
        max_length=20, choices=RecurrenceFrequency.choices, blank=True, null=True
    )
    recurrence_interval = models.PositiveIntegerField(default=1)
    recurrence_end_date = models.DateTimeField(blank=True, null=True)
    recurrence_max_occurrences = models.PositiveIntegerField(blank=True, null=True)
    recurrence_parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, blank=True, null=True, related_name='recurring_children'
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_trigger_type_display()})"


class TaskAutomationAction(models.Model):
    """Actions to execute when a task automation rule triggers."""

    class ActionType(models.TextChoices):
        CHANGE_STATUS = "change_status", _("Change Status")
        SET_PRIORITY = "set_priority", _("Set Priority")
        ASSIGN_USER = "assign_user", _("Assign User")
        UNASSIGN_USER = "unassign_user", _("Unassign User")
        ADD_LABEL = "add_label", _("Add Label")
        REMOVE_LABEL = "remove_label", _("Remove Label")
        SET_DUE_DATE = "set_due_date", _("Set Due Date")
        CLEAR_DUE_DATE = "clear_due_date", _("Clear Due Date")
        MOVE_TO_PROJECT = "move_to_project", _("Move to Project")
        SEND_NOTIFICATION = "send_notification", _("Send Notification")
        POST_COMMENT = "post_comment", _("Post Comment")
        ADD_TO_CALENDAR = "add_to_calendar", _("Add to Calendar")
        ARCHIVE_TASK = "archive_task", _("Archive Task")

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
    
    # Display conditions - button only shows when these conditions match
    show_on_status = models.JSONField(
        default=list,
        blank=True,
        help_text="List of task statuses where this button should appear (empty = all)"
    )
    show_on_priority = models.JSONField(
        default=list,
        blank=True,
        help_text="List of task priorities where this button should appear (empty = all)"
    )
    show_when_has_label = models.ForeignKey(
        TaskLabel,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="required_by_buttons",
        help_text="Button only shows when task has this label"
    )
    hide_when_has_label = models.ForeignKey(
        TaskLabel,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hidden_by_buttons",
        help_text="Button hides when task has this label"
    )
    
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
    
    def should_show_for_task(self, task: Task) -> bool:
        """Check if this button should be displayed for the given task."""
        # Check status condition
        if self.show_on_status and task.status not in self.show_on_status:
            return False
        
        # Check priority condition
        if self.show_on_priority and task.priority not in self.show_on_priority:
            return False
        
        # Check required label
        if self.show_when_has_label:
            if not task.label_assignments.filter(label=self.show_when_has_label).exists():
                return False
        
        # Check hidden label
        if self.hide_when_has_label:
            if task.label_assignments.filter(label=self.hide_when_has_label).exists():
                return False
        
        return True


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
