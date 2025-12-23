"""
Base automation engine for reusable automation logic.

Provides abstract base class for both Task and Board automation engines.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypeVar
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Generic type for Card or Task


class BaseAutomationEngine(ABC, Generic[T]):
    """
    Abstract base class for automation engines.

    Implements the Action Registry Pattern to avoid long if-elif chains.
    Subclasses must implement _build_action_registry() and _execute_rule().
    """

    def __init__(self, triggered_by=None):
        """
        Initialize the automation engine.

        Args:
            triggered_by: User who triggered the automation (optional)
        """
        self.triggered_by = triggered_by
        self._action_registry = self._build_action_registry()

    @abstractmethod
    def _build_action_registry(self) -> dict[str, Callable]:
        """
        Build the action type to handler mapping.

        Returns:
            Dict mapping action type strings to handler methods
        """
        pass

    @abstractmethod
    def _execute_rule(self, rule, entity: T):
        """
        Execute a single automation rule on an entity.

        Args:
            rule: Automation rule instance
            entity: Entity to apply rule to (Task or Card)

        Returns:
            Log entry for the execution
        """
        pass

    def _execute_rules(self, rules, entity: T) -> list:
        """
        Execute multiple automation rules on an entity.

        Args:
            rules: QuerySet or list of automation rules
            entity: Entity to apply rules to

        Returns:
            List of log entries
        """
        logs = []
        for rule in rules:
            log = self._execute_rule(rule, entity)
            logs.append(log)
        return logs

    def _execute_action(self, action, entity: T, config: dict) -> None:
        """
        Execute a single action on an entity using the registry pattern.

        Args:
            action: Action instance with action_type
            entity: Entity to apply action to
            config: Action configuration dict
        """
        action_handler = self._action_registry.get(action.action_type)

        if action_handler is None:
            logger.warning(f"Unknown action type: {action.action_type}")
            return

        try:
            action_handler(entity, config)
        except Exception as e:
            logger.error(f"Error executing action {action.action_type}: {e}")
            raise


class TriggerFilter:
    """
    Utility class for filtering automation rules based on trigger conditions.

    Provides static methods to check if a rule's trigger configuration matches
    the current event context.
    """

    @staticmethod
    def label_matches(rule, label) -> bool:
        """
        Check if rule's label filter matches the given label.

        Args:
            rule: Automation rule with trigger_config
            label: Label instance to check

        Returns:
            True if label matches or no filter is set
        """
        config = rule.trigger_config or {}
        target_label_id = config.get("label_id")
        if not target_label_id:
            return True
        return str(label.id) == str(target_label_id)

    @staticmethod
    def status_matches(rule, old_status: str, new_status: str) -> bool:
        """
        Check if rule's status filter matches the status change.

        Args:
            rule: Automation rule with trigger_config
            old_status: Previous status
            new_status: New status

        Returns:
            True if status matches or no filter is set
        """
        config = rule.trigger_config or {}
        target_status = config.get("to_status")
        source_status = config.get("from_status")

        if target_status and new_status != target_status:
            return False
        if source_status and old_status != source_status:
            return False
        return True

    @staticmethod
    def priority_matches(rule, old_priority: str, new_priority: str) -> bool:
        """
        Check if rule's priority filter matches the priority change.

        Args:
            rule: Automation rule with trigger_config
            old_priority: Previous priority
            new_priority: New priority

        Returns:
            True if priority matches or no filter is set
        """
        config = rule.trigger_config or {}
        target_priority = config.get("to_priority")

        if target_priority and new_priority != target_priority:
            return False
        return True

    @staticmethod
    def column_matches(rule, from_column, to_column) -> bool:
        """
        Check if rule's column filter matches the column change.

        Args:
            rule: Automation rule with trigger_config
            from_column: Source column
            to_column: Target column

        Returns:
            True if columns match or no filter is set
        """
        config = rule.trigger_config or {}
        target_column_id = config.get("to_column_id")
        source_column_id = config.get("from_column_id")

        if target_column_id and str(to_column.id) != str(target_column_id):
            return False
        if source_column_id and str(from_column.id) != str(source_column_id):
            return False
        return True

    @staticmethod
    def days_threshold_matches(rule, days: int) -> bool:
        """
        Check if days match the threshold in rule config.

        Args:
            rule: Automation rule with trigger_config
            days: Number of days to check

        Returns:
            True if days match threshold
        """
        config = rule.trigger_config or {}
        threshold_days = config.get("days_before", 3)
        return days == threshold_days

    @staticmethod
    def interval_matches(rule, days_overdue: int) -> bool:
        """
        Check if days_overdue matches the interval in rule config.

        Args:
            rule: Automation rule with trigger_config
            days_overdue: Number of days overdue

        Returns:
            True if interval matches (e.g., every N days)
        """
        config = rule.trigger_config or {}
        trigger_every_n_days = config.get("trigger_every_n_days", 1)
        return days_overdue % trigger_every_n_days == 0
