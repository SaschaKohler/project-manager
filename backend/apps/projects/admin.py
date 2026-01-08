from django.contrib import admin

from .models import (
    Event,
    Project,
    RecurringTask,
    Task,
    TaskAutomationAction,
    TaskAutomationLog,
    TaskAutomationRule,
    TaskButton,
    TaskButtonAction,
    TaskLabel,
    TaskLabelAssignment,
    TaskLink,
    TaskTimeEntry,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "title",
        "status",
        "category",
        "priority",
        "color",
        "created_at",
    )
    list_filter = ("status", "category", "priority", "color")
    search_fields = ("title", "organization__name")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "title",
        "status",
        "priority",
        "due_date",
        "assigned_to",
        "idea_card",
        "tracked_seconds",
    )
    list_filter = ("status", "priority")
    search_fields = ("title", "project__title")


@admin.register(RecurringTask)
class RecurringTaskAdmin(admin.ModelAdmin):
    list_display = (
        "task",
        "is_recurring",
        "recurrence_frequency",
        "recurrence_interval",
        "recurrence_end_date",
        "recurrence_max_occurrences",
    )
    list_filter = ("is_recurring", "recurrence_frequency")
    search_fields = ("task__title", "task__project__title")


@admin.register(TaskLink)
class TaskLinkAdmin(admin.ModelAdmin):
    list_display = ("url", "task", "created_at")
    search_fields = ("url", "title", "task__title")


@admin.register(TaskTimeEntry)
class TaskTimeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "user",
        "started_at",
        "stopped_at",
        "duration_seconds",
    )
    list_filter = ("user",)
    search_fields = ("task__title", "user__email")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "title", "type", "start_time", "end_time")
    list_filter = ("type",)
    search_fields = ("title", "project__title")


@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "color", "created_at")
    search_fields = ("name", "organization__name")
    list_filter = ("color",)


@admin.register(TaskLabelAssignment)
class TaskLabelAssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "label", "assigned_at")
    search_fields = ("task__title", "label__name")


class TaskAutomationActionInline(admin.TabularInline):
    model = TaskAutomationAction
    extra = 1


@admin.register(TaskAutomationRule)
class TaskAutomationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "project",
        "trigger_type",
        "is_active",
        "created_by",
        "created_at",
    )
    search_fields = ("name", "organization__name", "project__title")
    list_filter = ("trigger_type", "is_active")
    inlines = [TaskAutomationActionInline]


@admin.register(TaskAutomationAction)
class TaskAutomationActionAdmin(admin.ModelAdmin):
    list_display = ("rule", "action_type", "sort_order")
    search_fields = ("rule__name",)
    list_filter = ("action_type",)


@admin.register(TaskAutomationLog)
class TaskAutomationLogAdmin(admin.ModelAdmin):
    list_display = ("rule", "task", "status", "executed_at")
    search_fields = ("rule__name", "task__title")
    list_filter = ("status",)
    readonly_fields = ("rule", "task", "status", "message", "executed_at")


class TaskButtonActionInline(admin.TabularInline):
    model = TaskButtonAction
    extra = 1


@admin.register(TaskButton)
class TaskButtonAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "project",
        "icon",
        "color",
        "is_active",
        "created_by",
    )
    search_fields = ("name", "organization__name", "project__title")
    list_filter = ("is_active", "color")
    inlines = [TaskButtonActionInline]


@admin.register(TaskButtonAction)
class TaskButtonActionAdmin(admin.ModelAdmin):
    list_display = ("button", "action_type", "sort_order")
    search_fields = ("button__name",)
    list_filter = ("action_type",)
