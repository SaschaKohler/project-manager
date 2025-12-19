from django.contrib import admin

from .models import (
    AutomationAction,
    AutomationLog,
    AutomationRule,
    Board,
    BoardCard,
    BoardCardAttachment,
    BoardCardLabel,
    BoardCardLabelAssignment,
    BoardCardLink,
    BoardColumn,
    CardButton,
    CardButtonAction,
)


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "created_by", "created_at")
    search_fields = ("title", "organization__name")


@admin.register(BoardColumn)
class BoardColumnAdmin(admin.ModelAdmin):
    list_display = ("title", "board", "sort_order")
    search_fields = ("title", "board__title")


@admin.register(BoardCard)
class BoardCardAdmin(admin.ModelAdmin):
    list_display = ("title", "column", "sort_order", "created_by", "created_at")
    search_fields = ("title", "column__title", "column__board__title")


@admin.register(BoardCardLink)
class BoardCardLinkAdmin(admin.ModelAdmin):
    list_display = ("url", "card", "created_at")
    search_fields = ("url", "title", "card__title")


@admin.register(BoardCardAttachment)
class BoardCardAttachmentAdmin(admin.ModelAdmin):
    list_display = ("file", "card", "uploaded_by", "uploaded_at")
    search_fields = ("file", "card__title")


@admin.register(BoardCardLabel)
class BoardCardLabelAdmin(admin.ModelAdmin):
    list_display = ("name", "board", "color", "created_at")
    search_fields = ("name", "board__title")
    list_filter = ("color",)


@admin.register(BoardCardLabelAssignment)
class BoardCardLabelAssignmentAdmin(admin.ModelAdmin):
    list_display = ("card", "label", "assigned_at")
    search_fields = ("card__title", "label__name")


class AutomationActionInline(admin.TabularInline):
    model = AutomationAction
    extra = 1


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "board", "trigger_type", "is_active", "created_by", "created_at")
    search_fields = ("name", "board__title")
    list_filter = ("trigger_type", "is_active")
    inlines = [AutomationActionInline]


@admin.register(AutomationAction)
class AutomationActionAdmin(admin.ModelAdmin):
    list_display = ("rule", "action_type", "sort_order")
    search_fields = ("rule__name",)
    list_filter = ("action_type",)


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = ("rule", "card", "status", "executed_at")
    search_fields = ("rule__name", "card__title")
    list_filter = ("status",)
    readonly_fields = ("rule", "card", "status", "message", "executed_at")


class CardButtonActionInline(admin.TabularInline):
    model = CardButtonAction
    extra = 1


@admin.register(CardButton)
class CardButtonAdmin(admin.ModelAdmin):
    list_display = ("name", "board", "icon", "color", "is_active", "created_by")
    search_fields = ("name", "board__title")
    list_filter = ("is_active", "color")
    inlines = [CardButtonActionInline]


@admin.register(CardButtonAction)
class CardButtonActionAdmin(admin.ModelAdmin):
    list_display = ("button", "action_type", "sort_order")
    search_fields = ("button__name",)
    list_filter = ("action_type",)
