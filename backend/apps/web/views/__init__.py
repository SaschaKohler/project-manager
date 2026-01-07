"""
Web views module.

This module is organized by feature area for better maintainability:
- auth: Authentication and registration
- dashboard: Home and calendar views
- boards: Board and card management
- tasks: Task management
- projects: Project management
- team: Team and invitation management
- automations: Automation rules and buttons
- utils: Shared helper functions

Usage:
    from apps.web.views import tasks_page, tasks_create
    # or
    from apps.web.views.tasks import tasks_page, tasks_create
"""

# Authentication & Core
from .auth import healthz, register
from .dashboard import app_home, calendar_events, calendar_page
from .onboarding import onboarding, switch_org, workspaces_new
from .team import invite_accept, team_invite, team_page

# Projects
from .projects import (
    project_calendar_events,
    project_calendar_page,
    projects_archive,
    projects_archive_page,
    projects_complete,
    projects_create,
    projects_page,
    projects_restore,
)

# Boards
from .boards import (
    board_automation_rule_create,
    board_automation_rule_delete,
    board_automation_rule_toggle,
    board_automations_page,
    board_card_attachment_create,
    board_card_button_create,
    board_card_button_delete,
    board_card_button_execute,
    board_card_create,
    board_card_detail,
    board_card_link_create,
    board_card_move,
    board_detail_page,
    board_label_create,
    boards_create,
    boards_page,
)

# Tasks
from .tasks import (
    tasks_create,
    tasks_delete,
    tasks_delete_permanent,
    tasks_detail,
    tasks_move,
    tasks_page,
    tasks_restore,
    tasks_schedule,
    tasks_time_entries,
    tasks_timer,
    tasks_title,
    tasks_toggle,
    tasks_unschedule,
    tasks_assign,
    tasks_archive,
)

# Task automations
from .task_automations import (
    task_automation_rule_create,
    task_automation_rule_delete,
    task_automation_rule_toggle,
    task_automations,
    task_button_create,
    task_button_delete,
    task_button_execute,
    task_label_create,
)

# Utils
from .utils import (
    can_edit_task,
    get_org_member_user,
    humanize_seconds,
    require_task_edit_permission,
    task_event_style,
    web_shell_context,
)

# Export all for backwards compatibility
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
    "projects_archive",
    "projects_restore",
    "projects_archive_page",
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
