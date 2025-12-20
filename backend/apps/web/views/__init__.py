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

# Projects
from .projects import (
    project_calendar_events,
    project_calendar_page,
    projects_complete,
    projects_create,
    projects_page,
)

# Tasks - Main views (import remaining from old views.py as needed)
from .tasks import (
    tasks_create,
    tasks_page,
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
    # Projects
    "projects_page",
    "projects_create",
    "projects_complete",
    "project_calendar_page",
    "project_calendar_events",
    # Tasks
    "tasks_page",
    "tasks_create",
    # Utils
    "can_edit_task",
    "require_task_edit_permission",
    "humanize_seconds",
    "task_event_style",
    "web_shell_context",
    "get_org_member_user",
]

# NOTE: This is a partial migration. The following views still need to be migrated:
# - All remaining task views (tasks_detail, tasks_delete, tasks_timer, etc.)
# - All board views (boards_page, board_detail_page, etc.)
# - Team views (team_page, team_invite, etc.)
# - Automation views (board_automations_page, task_automations_page, etc.)
# 
# For now, import remaining views from the parent views.py file:
import sys
from pathlib import Path

# Import all non-migrated views from the old views.py
_old_views_path = Path(__file__).parent.parent / "views.py"
if _old_views_path.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_old_views", _old_views_path)
    if spec and spec.loader:
        _old_views = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_old_views)
        
        # Import all missing views from old file
        _missing_views = [
            # Onboarding & Workspace
            "onboarding", "workspaces_new", "switch_org",
            # Team
            "team_page", "team_invite", "invite_accept",
            # Boards
            "boards_page", "boards_create", "board_detail_page",
            "board_card_create", "board_card_detail", "board_card_move",
            "board_card_link_create", "board_card_attachment_create",
            "board_automations_page", "board_automation_rule_create",
            "board_automation_rule_toggle", "board_automation_rule_delete",
            "board_card_button_create", "board_card_button_delete",
            "board_card_button_execute", "board_label_create",
            # Tasks (remaining)
            "tasks_detail", "tasks_delete", "tasks_toggle", "tasks_timer",
            "tasks_time_entries", "tasks_title", "tasks_move",
            "tasks_schedule", "tasks_unschedule", "tasks_assign",
            "tasks_archive", "tasks_restore", "tasks_delete_permanent",
            "tasks_refresh",
            # Task Automations
            "task_automations", "task_automation_rule_create",
            "task_automation_rule_toggle", "task_automation_rule_delete",
            "task_button_create", "task_button_delete", "task_button_execute",
            "task_label_create", "task_label_assign", "task_label_remove",
        ]
        
        for view_name in _missing_views:
            if hasattr(_old_views, view_name):
                globals()[view_name] = getattr(_old_views, view_name)
                __all__.append(view_name)
