import uuid

from django.conf import settings
from django.db import models

from apps.tenants.models import Organization


class Board(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="boards"
    )
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_boards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class BoardColumn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="columns")
    title = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self) -> str:
        return f"{self.board.title}: {self.title}"


class BoardCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    column = models.ForeignKey(
        BoardColumn, on_delete=models.CASCADE, related_name="cards"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    due_date = models.DateTimeField(blank=True, null=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_board_cards",
        blank=True,
        null=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_board_cards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self) -> str:
        return self.title


class BoardCardLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(BoardCard, on_delete=models.CASCADE, related_name="links")
    title = models.CharField(max_length=255, blank=True, default="")
    url = models.URLField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.url


def _board_attachment_upload_to(instance: "BoardCardAttachment", filename: str) -> str:
    return f"boards/{instance.card_id}/{filename}"


class BoardCardAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(
        BoardCard, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=_board_attachment_upload_to)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="board_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.file.name


class BoardCardLabel(models.Model):
    """Labels that can be attached to cards."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="labels")
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default="gray")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("board", "name")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class BoardCardLabelAssignment(models.Model):
    """M2M through model for card labels."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(BoardCard, on_delete=models.CASCADE, related_name="label_assignments")
    label = models.ForeignKey(BoardCardLabel, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("card", "label")]


class AutomationRule(models.Model):
    """Automation rules for boards (like Trello Butler)."""

    class TriggerType(models.TextChoices):
        CARD_CREATED = "card_created", "Card Created"
        CARD_MOVED = "card_moved", "Card Moved"
        CARD_UPDATED = "card_updated", "Card Updated"
        DUE_DATE_APPROACHING = "due_date_approaching", "Due Date Approaching"
        DUE_DATE_REACHED = "due_date_reached", "Due Date Reached"
        DUE_DATE_OVERDUE = "due_date_overdue", "Due Date Overdue"
        LABEL_ADDED = "label_added", "Label Added"
        LABEL_REMOVED = "label_removed", "Label Removed"
        CHECKLIST_COMPLETED = "checklist_completed", "Checklist Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="automation_rules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    trigger_type = models.CharField(max_length=32, choices=TriggerType.choices)
    trigger_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_automation_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_trigger_type_display()})"


class AutomationAction(models.Model):
    """Actions to execute when an automation rule triggers."""

    class ActionType(models.TextChoices):
        MOVE_CARD = "move_card", "Move Card"
        MOVE_TO_TOP = "move_to_top", "Move to Top of List"
        MOVE_TO_BOTTOM = "move_to_bottom", "Move to Bottom of List"
        ASSIGN_USER = "assign_user", "Assign User"
        UNASSIGN_USER = "unassign_user", "Unassign User"
        ADD_LABEL = "add_label", "Add Label"
        REMOVE_LABEL = "remove_label", "Remove Label"
        SET_DUE_DATE = "set_due_date", "Set Due Date"
        CLEAR_DUE_DATE = "clear_due_date", "Clear Due Date"
        ADD_CHECKLIST = "add_checklist", "Add Checklist"
        SEND_NOTIFICATION = "send_notification", "Send Notification"
        POST_COMMENT = "post_comment", "Post Comment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=32, choices=ActionType.choices)
    action_config = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return f"{self.get_action_type_display()}"


class AutomationLog(models.Model):
    """Log of automation executions for debugging and audit."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name="logs")
    card = models.ForeignKey(BoardCard, on_delete=models.CASCADE, related_name="automation_logs")
    status = models.CharField(max_length=16, choices=Status.choices)
    message = models.TextField(blank=True, default="")
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]


class CardButton(models.Model):
    """Custom buttons that appear on cards for one-click actions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="card_buttons")
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default="play")
    color = models.CharField(max_length=20, default="indigo")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_card_buttons",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CardButtonAction(models.Model):
    """Actions to execute when a card button is clicked."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    button = models.ForeignKey(CardButton, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=32, choices=AutomationAction.ActionType.choices)
    action_config = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return f"{self.get_action_type_display()}"
