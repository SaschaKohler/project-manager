"""
Tests for web views and HTTP endpoints.
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime
from unittest.mock import patch

from apps.projects.models import Project, Task, TaskTimeEntry, TaskLabel
from apps.tenants.models import Organization, Membership


class TestDashboardViews:
    """Test cases for dashboard views."""

    def test_app_home_requires_login(self, client):
        """Test that dashboard requires login."""
        response = client.get(reverse("web:home"))
        assert response.status_code == 302  # Redirect to login

    def test_app_home_requires_active_org(self, authenticated_client):
        """Test that dashboard requires active organization."""
        response = authenticated_client.get(reverse("web:home"))
        assert response.status_code == 302  # Redirect to onboarding

    def test_app_home_dashboard_data(self, active_organization, authenticated_client):
        """Test dashboard displays correct data."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create some test data
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        task = Task.objects.create(
            project=project,
            title="Test Task",
            assigned_to=user
        )

        # Request dashboard
        response = authenticated_client.get(reverse("web:home"))

        assert response.status_code == 200
        assert "project_count" in response.context
        assert "task_count" in response.context
        assert response.context["project_count"] == 1
        assert response.context["task_count"] == 1

    def test_calendar_page_requires_login(self, client):
        """Test that calendar page requires login."""
        response = client.get(reverse("web:calendar"))
        assert response.status_code == 302  # Redirect to login

    def test_calendar_page_requires_active_org(self, authenticated_client):
        """Test that calendar page requires active organization."""
        response = authenticated_client.get(reverse("web:calendar"))
        assert response.status_code == 302  # Redirect to onboarding

    def test_calendar_page_data(self, active_organization, authenticated_client):
        """Test calendar page displays correct data."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create test project
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        # Request calendar page
        response = authenticated_client.get(reverse("web:calendar"))

        assert response.status_code == 200
        assert "projects" in response.context
        assert "members" in response.context
        assert list(response.context["projects"]) == [project]


class TestCalendarAPI:
    """Test cases for calendar API endpoints."""
    
    def test_calendar_events_requires_auth(self, client):
        """Test that calendar events API requires authentication."""
        response = client.get(reverse("web:calendar_events"))
        assert response.status_code == 302
    
    def test_calendar_events_requires_active_org(self, authenticated_client):
        """Test that calendar events API requires active organization."""
        response = authenticated_client.get(reverse("web:calendar_events"))
        assert response.status_code == 401
    
    def test_calendar_events_basic_functionality(self, active_organization, authenticated_client):
        """Test basic calendar events functionality."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create test project
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        # Create scheduled task
        scheduled_task = Task.objects.create(
            project=project,
            title="Scheduled Task",
            scheduled_start=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            assigned_to=user
        )

        # Request calendar events
        response = authenticated_client.get(reverse("web:calendar_events"))

        assert response.status_code == 200
        events = response.json()

        # Should have at least the scheduled task event
        assert len(events) >= 1

        # Find our task event
        task_event = next(
            (event for event in events if event.get("extendedProps", {}).get("task_title") == "Scheduled Task"),
            None
        )
        assert task_event is not None
        assert task_event["title"] == "Scheduled Task · " + user.email
        assert task_event["extendedProps"]["assigned_to"] == str(user.id)
    
    def test_calendar_events_filtering(self, active_organization, authenticated_client):
        """Test calendar events filtering parameters."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create test project
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        # Create tasks with different statuses
        todo_task = Task.objects.create(
            project=project,
            title="Todo Task",
            status=Task.Status.TODO,
            scheduled_start=timezone.now() + timedelta(days=1),
            assigned_to=user
        )

        done_task = Task.objects.create(
            project=project,
            title="Done Task",
            status=Task.Status.DONE,
            scheduled_start=timezone.now() + timedelta(days=2),
            assigned_to=user
        )

        # Test status filter
        response = authenticated_client.get(
            reverse("web:calendar_events") + "?status=TODO"
        )
        events = response.json()
        task_events = [e for e in events if not e.get("allDay")]
        assert len(task_events) == 1
        assert task_events[0]["extendedProps"]["status"] == "TODO"

        # Test hide_done filter
        response = authenticated_client.get(
            reverse("web:calendar_events") + "?hide_done=true"
        )
        events = response.json()
        task_events = [e for e in events if not e.get("allDay")]
        assert len(task_events) == 1  # Only TODO task
        assert task_events[0]["extendedProps"]["status"] == "TODO"

        # Test project filter
        response = authenticated_client.get(
            reverse("web:calendar_events") + f"?project={project.id}"
        )
        events = response.json()
        task_events = [e for e in events if not e.get("allDay")]
        assert len(task_events) == 2  # Both tasks
    
    def test_calendar_events_date_range(self, active_organization, authenticated_client):
        """Test calendar events date range filtering."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create test project
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        # Create tasks with different dates
        now = timezone.now()
        Task.objects.create(
            project=project,
            title="Today Task",
            scheduled_start=now,
            assigned_to=user
        )

        Task.objects.create(
            project=project,
            title="Future Task",
            scheduled_start=now + timedelta(days=10),
            assigned_to=user
        )

        # Test date range filtering
        start_date = (now + timedelta(days=5)).isoformat().replace('+', '%2B')
        end_date = (now + timedelta(days=15)).isoformat().replace('+', '%2B')

        response = authenticated_client.get(
            reverse("web:calendar_events") + f"?start={start_date}&end={end_date}"
        )
        events = response.json()
        task_events = [e for e in events if not e.get("allDay")]

        # Should only include future task
        assert len(task_events) == 1
        assert task_events[0]["extendedProps"]["task_title"] == "Future Task"
    
    def test_calendar_events_project_spans(self, active_organization, authenticated_client):
        """Test that project spans are included in calendar events."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create project with span dates
        start_date = timezone.now().date()
        end_date = (timezone.now() + timedelta(days=30)).date()

        project = Project.objects.create(
            organization=active_organization,
            title="Long Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        # Request calendar events
        response = authenticated_client.get(reverse("web:calendar_events"))
        events = response.json()

        # Find project span event
        project_span = next(
            (event for event in events if event.get("extendedProps", {}).get("kind") == "project_span"),
            None
        )
        assert project_span is not None
        assert project_span["title"] == "Long Project"
        assert project_span["allDay"] is True
        assert project_span["editable"] is False


class TestTaskViews:
    """Test cases for task-related views."""

    def test_task_detail_requires_login(self, client):
        """Test that task detail requires login."""
        response = client.get(reverse("web:tasks_detail", kwargs={"task_id": "12345678-1234-5678-9012-123456789012"}))
        assert response.status_code == 302  # Redirect to login

    def test_task_create_web_view(self, authenticated_client, organization_factory, project_factory, user_factory):
        """Test task creation via web view."""
        user = user_factory()
        authenticated_client.force_login(user)
        org = organization_factory(user=user)
        authenticated_client.session["active_org_id"] = str(org.id)
        authenticated_client.session.save()

        # Create test project
        project = project_factory(organization=org, created_by=user)

        # Test task creation
        data = {
            "title": "New Test Task",
            "project_id": str(project.id),
            "assigned_to": str(user.id),
        }

        response = authenticated_client.post(reverse("web:tasks_create"), data, headers={"HX-Request": "true"})

        # Should return HTMX response (rendered template)
        assert response.status_code == 200
        # Check that task was created
        task = Task.objects.filter(title="New Test Task", project=project).first()
        assert task is not None
        assert task.assigned_to == user

    def test_task_archive_view(self, active_organization, authenticated_client):
        """Test task archive view."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create test project and task
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        task = Task.objects.create(
            project=project,
            title="Archive Task",
            assigned_to=user
        )

        # Request archive page
        response = authenticated_client.get(reverse("web:tasks_archive"))

        assert response.status_code == 200
        assert "archived_tasks" in response.context
        # Should include archived tasks
        archived_tasks = list(response.context["archived_tasks"])
        assert len(archived_tasks) == 0  # No archived tasks yet


class TestProjectViews:
    """Test cases for project-related views."""

    def test_project_page_requires_login(self, client):
        """Test that project page requires login."""
        response = client.get(reverse("web:projects"))
        assert response.status_code == 302  # Redirect to login

    def test_project_page_data(self, active_organization, authenticated_client):
        """Test project page displays correct data."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create test project
        project = Project.objects.create(
            organization=active_organization,
            title="Test Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user
        )

        # Request project page
        response = authenticated_client.get(reverse("web:projects"))

        assert response.status_code == 200
        assert "projects" in response.context
        assert project in response.context["projects"]

    def test_project_archive_page(self, active_organization, authenticated_client):
        """Test archived projects page."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create active and archived projects
        active_project = Project.objects.create(
            organization=active_organization,
            title="Active Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user,
            is_archived=False
        )

        archived_project = Project.objects.create(
            organization=active_organization,
            title="Archived Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user,
            is_archived=True,
            archived_at=timezone.now()
        )

        # Request archive page
        response = authenticated_client.get(reverse("web:projects_archive_page"))

        assert response.status_code == 200
        assert "archived_projects" in response.context
        archived_projects = list(response.context["archived_projects"])
        assert len(archived_projects) == 1
        assert archived_projects[0] == archived_project

    def test_project_page_filters_archived(self, active_organization, authenticated_client):
        """Test that project page filters out archived projects."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Create active and archived projects
        active_project = Project.objects.create(
            organization=active_organization,
            title="Active Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user,
            is_archived=False
        )

        archived_project = Project.objects.create(
            organization=active_organization,
            title="Archived Project",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=user,
            is_archived=True,
            archived_at=timezone.now()
        )

        # Request projects page
        response = authenticated_client.get(reverse("web:projects"))

        assert response.status_code == 200
        assert "projects" in response.context
        projects = list(response.context["projects"])
        assert len(projects) == 1
        assert projects[0] == active_project
        assert archived_project not in projects


class TestTeamViews:
    """Test cases for team-related views."""
    
    def test_team_page_requires_login(self, client):
        """Test that team page requires login."""
        response = client.get(reverse("web:team"))
        assert response.status_code == 302  # Redirect to login

    def test_team_invite_accept_requires_token(self, client):
        """Test that team invite accept requires valid token."""
        response = client.get(reverse("web:invite_accept", kwargs={"token": "12345678-1234-5678-9012-123456789012"}))
        assert response.status_code == 302  # Redirect to login since not authenticated

    def test_team_page_data(self, active_organization, authenticated_client):
        """Test team page displays correct data."""
        user = active_organization.memberships.first().user
        authenticated_client.force_login(user)

        # Request team page
        response = authenticated_client.get(reverse("web:team"))

        assert response.status_code == 200
        assert "org" in response.context
        assert response.context["org"] == active_organization


class TestOnboardingViews:
    """Test cases for onboarding views."""
    
    def test_onboarding_page(self, client):
        """Test onboarding page accessibility."""
        response = client.get(reverse("web:onboarding"))
        assert response.status_code in [200, 302]  # May redirect if already has org
    
    def test_onboarding_create_organization(self, authenticated_client):
        """Test organization creation via onboarding."""
        # This would test the organization creation process
        # Implementation depends on the actual onboarding flow
        pass


class TestAuthenticationViews:
    """Test cases for authentication views."""
    
    def test_login_page(self, client):
        """Test login page accessibility."""
        response = client.get(reverse("login"))
        assert response.status_code == 200

    def test_register_page(self, client):
        """Test registration page accessibility."""
        response = client.get(reverse("web_register"))
        assert response.status_code == 200

    def test_logout(self, authenticated_client):
        """Test logout functionality."""
        response = authenticated_client.post(reverse("logout"))
        assert response.status_code == 302  # Redirect after logout

        # Verify user is logged out
        response = authenticated_client.get(reverse("web:home"))
        assert response.status_code == 302  # Should redirect to login


class TestMiddleware:
    """Test cases for custom middleware."""
    
    def test_active_organization_middleware(self, authenticated_client, organization_factory):
        """Test ActiveOrganizationMiddleware functionality."""
        # Create organization
        org = organization_factory()

        # Set active organization in session
        authenticated_client.session["active_org_id"] = str(org.id)
        authenticated_client.session.save()

        # Request should have active_org in context
        response = authenticated_client.get(reverse("web:home"))
        # This test would depend on how the middleware sets the active_org

    def test_active_organization_middleware_no_org(self, authenticated_client):
        """Test ActiveOrganizationMiddleware when no organization is set."""
        # Request without active organization
        response = authenticated_client.get(reverse("web:home"))
        assert response.status_code == 302  # Should redirect to onboarding