"""
Automation Engine for Board Cards.

Handles trigger detection and action execution for automation rules.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model
    User = get_user_model()

from .models import (
    AutomationAction,
    AutomationLog,
    AutomationRule,
    BoardCard,
    BoardCardLabel,
    BoardCardLabelAssignment,
    BoardColumn,
)

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Engine to process automation rules and execute actions."""

    def __init__(self, triggered_by: "User | None" = None):
        self.triggered_by = triggered_by

    def trigger_card_created(self, card: BoardCard) -> list[AutomationLog]:
        """Trigger automation rules when a card is created."""
        rules = AutomationRule.objects.filter(
            board=card.column.board,
            trigger_type=AutomationRule.TriggerType.CARD_CREATED,
            is_active=True,
        ).prefetch_related("actions")

        return self._execute_rules(rules, card)

    def trigger_card_moved(
        self,
        card: BoardCard,
        from_column: BoardColumn,
        to_column: BoardColumn,
    ) -> list[AutomationLog]:
        """Trigger automation rules when a card is moved to a different column."""
        rules = AutomationRule.objects.filter(
            board=card.column.board,
            trigger_type=AutomationRule.TriggerType.CARD_MOVED,
            is_active=True,
        ).prefetch_related("actions")

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}

            # Check if rule has column filter
            target_column_id = config.get("to_column_id")
            source_column_id = config.get("from_column_id")

            # Skip if rule specifies a target column and it doesn't match
            if target_column_id and str(to_column.id) != str(target_column_id):
                continue

            # Skip if rule specifies a source column and it doesn't match
            if source_column_id and str(from_column.id) != str(source_column_id):
                continue

            log = self._execute_rule(rule, card)
            logs.append(log)

        return logs

    def trigger_card_updated(self, card: BoardCard) -> list[AutomationLog]:
        """Trigger automation rules when a card is updated."""
        rules = AutomationRule.objects.filter(
            board=card.column.board,
            trigger_type=AutomationRule.TriggerType.CARD_UPDATED,
            is_active=True,
        ).prefetch_related("actions")

        return self._execute_rules(rules, card)

    def trigger_label_added(self, card: BoardCard, label: BoardCardLabel) -> list[AutomationLog]:
        """Trigger automation rules when a label is added to a card."""
        rules = AutomationRule.objects.filter(
            board=card.column.board,
            trigger_type=AutomationRule.TriggerType.LABEL_ADDED,
            is_active=True,
        ).prefetch_related("actions")

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            target_label_id = config.get("label_id")

            # Skip if rule specifies a label and it doesn't match
            if target_label_id and str(label.id) != str(target_label_id):
                continue

            log = self._execute_rule(rule, card)
            logs.append(log)

        return logs

    def trigger_label_removed(self, card: BoardCard, label: BoardCardLabel) -> list[AutomationLog]:
        """Trigger automation rules when a label is removed from a card."""
        rules = AutomationRule.objects.filter(
            board=card.column.board,
            trigger_type=AutomationRule.TriggerType.LABEL_REMOVED,
            is_active=True,
        ).prefetch_related("actions")

        logs = []
        for rule in rules:
            config = rule.trigger_config or {}
            target_label_id = config.get("label_id")

            if target_label_id and str(label.id) != str(target_label_id):
                continue

            log = self._execute_rule(rule, card)
            logs.append(log)

        return logs

    def _execute_rules(self, rules, card: BoardCard) -> list[AutomationLog]:
        """Execute a queryset of rules for a card."""
        logs = []
        for rule in rules:
            log = self._execute_rule(rule, card)
            logs.append(log)
        return logs

    def _execute_rule(self, rule: AutomationRule, card: BoardCard) -> AutomationLog:
        """Execute all actions for a single rule."""
        try:
            with transaction.atomic():
                for action in rule.actions.all():
                    self._execute_action(action, card)

            return AutomationLog.objects.create(
                rule=rule,
                card=card,
                status=AutomationLog.Status.SUCCESS,
                message=_("Rule executed successfully"),
            )
        except Exception as exc:
            logger.exception("Automation rule %s failed for card %s", rule.id, card.id)
            return AutomationLog.objects.create(
                rule=rule,
                card=card,
                status=AutomationLog.Status.FAILED,
                message=str(exc),
            )

    def _execute_action(self, action: AutomationAction, card: BoardCard) -> None:
        """Execute a single action on a card."""
        config = action.action_config or {}
        action_type = action.action_type

        if action_type == AutomationAction.ActionType.MOVE_CARD:
            self._action_move_card(card, config)
        elif action_type == AutomationAction.ActionType.MOVE_TO_TOP:
            self._action_move_to_top(card)
        elif action_type == AutomationAction.ActionType.MOVE_TO_BOTTOM:
            self._action_move_to_bottom(card)
        elif action_type == AutomationAction.ActionType.ADD_LABEL:
            self._action_add_label(card, config)
        elif action_type == AutomationAction.ActionType.REMOVE_LABEL:
            self._action_remove_label(card, config)
        elif action_type == AutomationAction.ActionType.SET_DUE_DATE:
            self._action_set_due_date(card, config)
        elif action_type == AutomationAction.ActionType.CLEAR_DUE_DATE:
            self._action_clear_due_date(card)
        elif action_type == AutomationAction.ActionType.ASSIGN_USER:
            self._action_assign_user(card, config)
        elif action_type == AutomationAction.ActionType.UNASSIGN_USER:
            self._action_unassign_user(card)
        elif action_type == AutomationAction.ActionType.SEND_NOTIFICATION:
            self._action_send_notification(card, config)
        elif action_type == AutomationAction.ActionType.POST_COMMENT:
            self._action_post_comment(card, config)

    def _action_move_card(self, card: BoardCard, config: dict) -> None:
        """Move card to a different column."""
        target_column_id = config.get("column_id")
        if not target_column_id:
            return

        target_column = BoardColumn.objects.filter(
            id=target_column_id,
            board=card.column.board,
        ).first()

        if target_column and target_column.id != card.column_id:
            from django.db.models import Max
            max_sort = BoardCard.objects.filter(column=target_column).aggregate(
                max=Max("sort_order")
            ).get("max")
            card.column = target_column
            card.sort_order = int(max_sort or 0) + 1
            card.save(update_fields=["column", "sort_order"])

    def _action_move_to_top(self, card: BoardCard) -> None:
        """Move card to top of its current column."""
        from django.db.models import Min
        min_sort = BoardCard.objects.filter(column=card.column).exclude(id=card.id).aggregate(
            min=Min("sort_order")
        ).get("min")
        card.sort_order = max(0, int(min_sort or 1) - 1)
        card.save(update_fields=["sort_order"])

    def _action_move_to_bottom(self, card: BoardCard) -> None:
        """Move card to bottom of its current column."""
        from django.db.models import Max
        max_sort = BoardCard.objects.filter(column=card.column).exclude(id=card.id).aggregate(
            max=Max("sort_order")
        ).get("max")
        card.sort_order = int(max_sort or 0) + 1
        card.save(update_fields=["sort_order"])

    def _action_add_label(self, card: BoardCard, config: dict) -> None:
        """Add a label to the card."""
        label_id = config.get("label_id")
        if not label_id:
            return

        label = BoardCardLabel.objects.filter(
            id=label_id,
            board=card.column.board,
        ).first()

        if label:
            BoardCardLabelAssignment.objects.get_or_create(card=card, label=label)

    def _action_remove_label(self, card: BoardCard, config: dict) -> None:
        """Remove a label from the card."""
        label_id = config.get("label_id")
        if not label_id:
            return

        BoardCardLabelAssignment.objects.filter(card=card, label_id=label_id).delete()

    def _action_set_due_date(self, card: BoardCard, config: dict) -> None:
        """Set due date on the card."""
        days_offset = config.get("days_offset", 3)
        card.due_date = timezone.now() + timedelta(days=int(days_offset))
        card.save(update_fields=["due_date"])

    def _action_clear_due_date(self, card: BoardCard) -> None:
        """Clear due date from the card."""
        card.due_date = None
        card.save(update_fields=["due_date"])

    def _action_assign_user(self, card: BoardCard, config: dict) -> None:
        """Assign a user to the card."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_id = config.get("user_id")
        assign_triggered_by = config.get("assign_triggered_by", False)

        if assign_triggered_by and self.triggered_by:
            card.assigned_to = self.triggered_by
            card.save(update_fields=["assigned_to"])
        elif user_id:
            user = User.objects.filter(id=user_id, is_active=True).first()
            if user:
                card.assigned_to = user
                card.save(update_fields=["assigned_to"])

    def _action_unassign_user(self, card: BoardCard) -> None:
        """Unassign user from the card."""
        card.assigned_to = None
        card.save(update_fields=["assigned_to"])

    def _action_send_notification(self, card: BoardCard, config: dict) -> None:
        """Send a notification (placeholder for future implementation)."""
        # TODO: Implement notification system
        message = config.get("message", "")
        logger.info("Notification for card %s: %s", card.id, message)

    def _action_post_comment(self, card: BoardCard, config: dict) -> None:
        """Post a comment on the card (placeholder for future implementation)."""
        # TODO: Implement comment system
        comment = config.get("comment", "")
        logger.info("Comment for card %s: %s", card.id, comment)


def execute_card_button(button_id: str, card: BoardCard, triggered_by: "User") -> bool:
    """Execute all actions for a card button."""
    from .models import CardButton

    button = CardButton.objects.filter(id=button_id, is_active=True).prefetch_related("actions").first()
    if not button:
        return False

    engine = AutomationEngine(triggered_by=triggered_by)

    try:
        with transaction.atomic():
            for action in button.actions.all():
                # CardButtonAction uses same action types as AutomationAction
                fake_action = AutomationAction(
                    action_type=action.action_type,
                    action_config=action.action_config,
                )
                engine._execute_action(fake_action, card)
        return True
    except Exception:
        logger.exception("Card button %s failed for card %s", button_id, card.id)
        return False
