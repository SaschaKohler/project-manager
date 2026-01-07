"""
Web views forwarding module.

This file now forwards all view imports to the modular structure.
All views have been migrated to individual modules in the views/ directory.
"""

# Import all views from the modular structure
from . import *

# For backwards compatibility, also import directly
from .auth import *
from .dashboard import *
from .boards import *
from .tasks import *
from .projects import *
from .team import *
from .task_automations import *
from .onboarding import *
from .utils import *

__all__ = [
    # Auth
    "healthz",
    "register",
    # Dashboard
    "app_home",
    "calendar_page",
    "calendar_events",
    # Onboarding & workspace
    "onboarding",
    "workspaces_new",
    "switch_org",
    # Team
    "team_page",
    "team_invite",
    "invite_accept",
    # Projects
    "projects_page",
    "projects_create",
    "projects_complete",
    "project_calendar_page",
    "project_calendar_events",
    # Boards
    "boards_page",
    "boards_create",
    "board_detail_page",
    "board_card_create",
    "board_card_detail",
    "board_card_move",
    "board_card_link_create",
    "board_card_attachment_create",
    "board_automations_page",
    "board_automation_rule_create",
    "board_automation_rule_toggle",
    "board_automation_rule_delete",
    "board_card_button_create",
    "board_card_button_delete",
    "board_card_button_execute",
    "board_label_create",
    # Tasks
    "tasks_page",
    "tasks_create",
    "tasks_detail",
    "tasks_delete",
    "tasks_toggle",
    "tasks_timer",
    "tasks_time_entries",
    "tasks_title",
    "tasks_move",
    "tasks_schedule",
    "tasks_unschedule",
    "tasks_assign",
    "tasks_archive",
    "tasks_restore",
    "tasks_delete_permanent",
    # Task automations
    "task_automations",
    "task_automation_rule_create",
    "task_automation_rule_toggle",
    "task_automation_rule_delete",
    "task_button_create",
    "task_button_delete",
    "task_button_execute",
    "task_label_create",
    # Utils
    "can_edit_task",
    "require_task_edit_permission",
    "humanize_seconds",
    "task_event_style",
    "web_shell_context",
    "get_org_member_user",
]
