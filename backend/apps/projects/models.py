import uuid

from django.conf import settings
from django.db import models

from apps.tenants.models import Organization


class Project(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Category(models.TextChoices):
        WORKSHOP = "WORKSHOP", "Workshop"
        RETREAT = "RETREAT", "Retreat"
        CONSULTATION = "CONSULTATION", "Consultation"
        IT_SERVICE = "IT_SERVICE", "IT Service"
        MARKETING = "MARKETING", "Marketing"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.WORKSHOP)
    budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


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
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateTimeField(blank=True, null=True)
    scheduled_start = models.DateTimeField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tasks")
    tracked_seconds = models.PositiveIntegerField(default=0)
    progress = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
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
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_time_entries")
    started_at = models.DateTimeField()
    stopped_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.task_id} · {self.user_id} · {self.started_at}"


class Event(models.Model):
    class Type(models.TextChoices):
        SESSION = "SESSION", "Session"
        MARKETING = "MARKETING", "Marketing"
        DEADLINE = "DEADLINE", "Deadline"
        MEETING = "MEETING", "Meeting"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="events")
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
