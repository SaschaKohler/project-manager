"""
Shared utility functions for web views.

Contains helper functions used across multiple view modules.
"""
from django.http import HttpResponse
from django.utils.translation import gettext as _

from apps.projects.models import Task
from apps.tenants.models import Membership


def can_edit_task(request, task: Task) -> bool:
    """
    Check if the current user has permission to edit a task.
    
    Users can edit a task if they are:
    - Organization owner or admin
    - The task assignee
    - Creator of the linked idea card (if any)
    
    Args:
        request: HTTP request with active_org and user
        task: Task instance to check permissions for
        
    Returns:
        True if user can edit, False otherwise
    """
    org = request.active_org
    if org is None:
        return False

    membership = Membership.objects.filter(
        organization=org, user=request.user
    ).only("role").first()
    
    if membership is None:
        return False

    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return True

    if getattr(task, "idea_card_id", None):
        try:
            if task.idea_card and getattr(task.idea_card, "created_by_id", None) == request.user.id:
                return True
        except Exception:  # noqa: BLE001
            pass

    return task.assigned_to_id == request.user.id


def require_task_edit_permission(request, task: Task) -> HttpResponse | None:
    """
    Require task edit permission or return 403 response.
    
    Args:
        request: HTTP request
        task: Task to check permissions for
        
    Returns:
        None if user has permission, 403 HttpResponse otherwise
    """
    if can_edit_task(request, task):
        return None
    return HttpResponse("", status=403)


def humanize_seconds(seconds: int) -> str:
    """
    Convert seconds to human-readable time format.
    
    Args:
        seconds: Number of seconds
        
    Returns:
        Formatted string like "2h 30m" or "45m"
    """
    seconds = int(seconds or 0)
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def task_event_style(status: str) -> dict:
    """
    Get calendar event styling based on task status.
    
    Args:
        status: Task status (TODO, IN_PROGRESS, DONE)
        
    Returns:
        Dict with backgroundColor, borderColor, textColor
    """
    if status == Task.Status.IN_PROGRESS:
        return {
            "backgroundColor": "rgba(16, 185, 129, 0.85)",
            "borderColor": "rgba(16, 185, 129, 1)",
            "textColor": "rgb(244, 244, 245)",
        }
    if status == Task.Status.DONE:
        return {
            "backgroundColor": "rgba(59, 130, 246, 0.85)",
            "borderColor": "rgba(59, 130, 246, 1)",
            "textColor": "rgb(244, 244, 245)",
        }
    return {
        "backgroundColor": "rgba(161, 161, 170, 0.85)",
        "borderColor": "rgba(161, 161, 170, 1)",
        "textColor": "rgb(244, 244, 245)",
    }


def _project_color_rgb(color: str) -> tuple[int, int, int]:
    palette = {
        "indigo": (99, 102, 241),
        "emerald": (16, 185, 129),
        "sky": (14, 165, 233),
        "violet": (139, 92, 246),
        "rose": (244, 63, 94),
        "amber": (245, 158, 11),
        "teal": (20, 184, 166),
        "orange": (249, 115, 22),
        "lime": (132, 204, 22),
        "fuchsia": (217, 70, 239),
    }
    key = (color or "").strip().lower()
    return palette.get(key, palette["indigo"])


def _rgba(rgb: tuple[int, int, int], alpha: float) -> str:
    r, g, b = rgb
    return f"rgba({r}, {g}, {b}, {alpha})"


def project_span_event_style(project_color: str) -> dict:
    rgb = _project_color_rgb(project_color)
    return {
        "backgroundColor": _rgba(rgb, 0.26),
        "borderColor": _rgba(rgb, 0.85),
        "textColor": "rgb(244, 244, 245)",
    }


def task_event_style_for_project(status: str, project_color: str) -> dict:
    rgb = _project_color_rgb(project_color)
    if status == Task.Status.IN_PROGRESS:
        return {
            "backgroundColor": _rgba(rgb, 0.85),
            "borderColor": _rgba(rgb, 1.0),
            "textColor": "rgb(244, 244, 245)",
        }
    if status == Task.Status.DONE:
        return {
            "backgroundColor": _rgba(rgb, 0.28),
            "borderColor": _rgba(rgb, 0.55),
            "textColor": "rgb(244, 244, 245)",
        }
    return {
        "backgroundColor": _rgba(rgb, 0.60),
        "borderColor": _rgba(rgb, 0.90),
        "textColor": "rgb(244, 244, 245)",
    }


def web_shell_context(request) -> dict:
    """
    Get common context data for all web pages.
    
    Includes active organization and user membership information.
    
    Args:
        request: HTTP request with active_org
        
    Returns:
        Dict with org, orgs, active_org, user_membership, and is_owner
    """
    from apps.tenants.models import Organization
    
    membership = None
    is_owner = False
    
    if request.active_org is not None:
        membership = Membership.objects.filter(
            organization=request.active_org, 
            user=request.user
        ).only("role").first()
        
        if membership:
            is_owner = membership.role == Membership.Role.OWNER
    
    return {
        "org": request.active_org,
        "active_org": request.active_org,
        "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
        "user_membership": membership,
        "is_owner": is_owner,
    }


def get_org_member_user(org, user_id_raw: str):
    """
    Get an active user who is a member of the organization.
    
    Args:
        org: Organization instance
        user_id_raw: User ID as string
        
    Returns:
        User instance if found and active, None otherwise
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user_id_raw = (user_id_raw or "").strip()
    if not user_id_raw:
        return None
    
    from apps.tenants.models import Membership
    if not Membership.objects.filter(organization=org, user_id=user_id_raw).exists():
        return None
    
    return User.objects.filter(id=user_id_raw, is_active=True).first()
