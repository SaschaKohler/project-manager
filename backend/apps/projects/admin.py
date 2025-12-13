from django.contrib import admin

from .models import Event, Project, Task, TaskLink, TaskTimeEntry


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "title", "status", "category", "priority", "created_at")
    list_filter = ("status", "category", "priority")
    search_fields = ("title", "organization__name")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "title", "status", "priority", "due_date", "assigned_to", "idea_card", "tracked_seconds")
    list_filter = ("status", "priority")
    search_fields = ("title", "project__title")


@admin.register(TaskLink)
class TaskLinkAdmin(admin.ModelAdmin):
    list_display = ("url", "task", "created_at")
    search_fields = ("url", "title", "task__title")


@admin.register(TaskTimeEntry)
class TaskTimeEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "user", "started_at", "stopped_at", "duration_seconds")
    list_filter = ("user",)
    search_fields = ("task__title", "user__email")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "title", "type", "start_time", "end_time")
    list_filter = ("type",)
    search_fields = ("title", "project__title")
