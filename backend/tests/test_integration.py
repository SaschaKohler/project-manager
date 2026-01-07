"""
Integration tests for key application workflows.
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.projects.models import Project, Task, TaskAutomationRule, TaskAutomationAction
from apps.tenants.models import Organization, Membership


class TestProjectTaskWorkflow:
    """Integration tests for project and task management workflow."""

    def test_complete_project_task_workflow(self, authenticated_client, organization_factory, user_factory):
        """Test the complete workflow of creating a project, adding tasks, and managing them."""
        # Setup
        org = organization_factory()
        user = user_factory()
        Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)

        # Set active organization
        authenticated_client.session["active_org_id"] = str(org.id)
        authenticated_client.session.save()

        # 1. Create a project
        project_data = {
            "title": "Integration Test Project",
            "description": "Testing the full workflow",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "category": "DEVELOPMENT",
            "priority": "HIGH",
            "color": "blue"
        }

        response = authenticated_client.post(reverse("web:projects_create"), project_data)
        assert response.status_code == 302  # Redirect after creation

        # Verify project was created
        project = Project.objects.get(title="Integration Test Project")
        assert project.organization == org
        assert project.created_by == user

        # 2. Create tasks for the project
        task_data = {
            "project": str(project.id),
            "title": "First Task",
            "description": "This is the first task",
            "status": "TODO",
            "priority": "HIGH",
            "assigned_to": str(user.id)
        }

        response = authenticated_client.post(reverse("web:tasks_create"), task_data)
        assert response.status_code == 302

        # Verify task was created
        task = Task.objects.get(title="First Task")
        assert task.project == project
        assert task.assigned_to == user
        assert task.status == Task.Status.TODO

        # 3. Update task status
        update_data = {
            "status": "IN_PROGRESS"
        }

        response = authenticated_client.post(
            reverse("web:tasks_toggle", kwargs={"task_id": task.id}),
            update_data
        )
        assert response.status_code == 302

        # Verify status changed
        task.refresh_from_db()
        assert task.status == Task.Status.IN_PROGRESS

        # 4. Add time tracking
        timer_data = {
            "action": "start"
        }

        response = authenticated_client.post(
            reverse("web:tasks_timer", kwargs={"task_id": task.id}),
            timer_data
        )
        assert response.status_code == 302

        # Stop timer after some time
        import time
        time.sleep(0.1)  # Small delay

        timer_data = {
            "action": "stop"
        }

        response = authenticated_client.post(
            reverse("web:tasks_timer", kwargs={"task_id": task.id}),
            timer_data
        )
        assert response.status_code == 302

        # Verify time was tracked
        task.refresh_from_db()
        assert task.tracked_seconds > 0


class TestAutomationWorkflow:
    """Integration tests for automation workflows."""

    def test_task_automation_workflow(self, authenticated_client, organization_factory, user_factory, project_factory, task_factory):
        """Test the complete automation workflow."""
        # Setup
        org = organization_factory()
        user = user_factory()
        project = project_factory(organization=org, created_by=user)
        Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)

        # Set active organization
        authenticated_client.session["active_org_id"] = str(org.id)
        authenticated_client.session.save()

        # 1. Create an automation rule
        rule_data = {
            "name": "Auto-complete high priority tasks",
            "trigger_type": "status_changed",
            "trigger_config": '{"to_status": "DONE"}',
            "description": "Automatically archive completed tasks"
        }

        response = authenticated_client.post(reverse("web:task_automation_rule_create"), rule_data)
        assert response.status_code == 302

        # Verify rule was created
        rule = TaskAutomationRule.objects.get(name="Auto-complete high priority tasks")
        assert rule.organization == org
        assert rule.trigger_type == TaskAutomationRule.TriggerType.STATUS_CHANGED
        assert rule.is_active is True

        # 2. Add automation action
        action_data = {
            "rule": str(rule.id),
            "action_type": "archive_task",
            "action_config": "{}"
        }

        # Since we don't have a direct endpoint, create via model
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.ARCHIVE_TASK,
            action_config={}
        )

        # 3. Create a task and trigger automation
        task = task_factory(project=project, assigned_to=user, status=Task.Status.IN_PROGRESS)

        # Change task status to DONE (should trigger automation)
        task.status = Task.Status.DONE
        task.save()

        # Check if automation ran (task should be archived)
        task.refresh_from_db()
        assert task.is_archived is True
        assert task.archived_at is not None


class TestTeamCollaborationWorkflow:
    """Integration tests for team collaboration features."""

    def test_team_invitation_workflow(self, authenticated_client, organization_factory, user_factory):
        """Test the team invitation and acceptance workflow."""
        # Setup
        org = organization_factory()
        owner = user_factory()
        Membership.objects.create(organization=org, user=owner, role=Membership.Role.OWNER)

        # Set active organization
        authenticated_client.session["active_org_id"] = str(org.id)
        authenticated_client.session.save()

        # 1. Send team invitation
        invite_data = {
            "email": "newmember@example.com",
            "role": "MEMBER"
        }

        response = authenticated_client.post(reverse("web:team_invite"), invite_data)
        assert response.status_code == 302

        # Verify invitation was created
        from apps.tenants.models import OrganizationInvitation
        invitation = OrganizationInvitation.objects.get(email="newmember@example.com")
        assert invitation.organization == org
        assert invitation.invited_by == owner
        assert invitation.status == OrganizationInvitation.Status.PENDING

        # 2. Accept invitation (simulate with a new client)
        from django.test import Client
        new_client = Client()

        # Create the invited user
        invited_user = user_factory(email="newmember@example.com")

        # Accept invitation
        accept_data = {
            "token": str(invitation.token)
        }

        response = new_client.post(reverse("web:invite_accept", kwargs={"token": invitation.token}), accept_data)
        assert response.status_code == 302

        # Verify membership was created
        membership = Membership.objects.get(organization=org, user=invited_user)
        assert membership.role == Membership.Role.MEMBER

        # Verify invitation status changed
        invitation.refresh_from_db()
        assert invitation.status == OrganizationInvitation.Status.ACCEPTED


class TestCalendarWorkflow:
    """Integration tests for calendar functionality."""

    def test_calendar_event_workflow(self, authenticated_client, organization_factory, user_factory, project_factory, task_factory):
        """Test calendar event creation and filtering."""
        # Setup
        org = organization_factory()
        user = user_factory()
        project = project_factory(organization=org, created_by=user)
        Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)

        # Set active organization
        authenticated_client.session["active_org_id"] = str(org.id)
        authenticated_client.session.save()

        # 1. Create scheduled tasks
        now = timezone.now()
        scheduled_task = task_factory(
            project=project,
            assigned_to=user,
            title="Scheduled Task",
            scheduled_start=now + timedelta(days=1),
            duration_minutes=60
        )

        overdue_task = task_factory(
            project=project,
            assigned_to=user,
            title="Overdue Task",
            due_date=now - timedelta(days=1)
        )

        # 2. Request calendar events
        response = authenticated_client.get(reverse("web:calendar_events"))
        assert response.status_code == 200

        events = response.json()

        # Should include the scheduled task
        scheduled_events = [e for e in events if e.get("extendedProps", {}).get("task_title") == "Scheduled Task"]
        assert len(scheduled_events) == 1

        task_event = scheduled_events[0]
        assert task_event["extendedProps"]["assigned_to"] == str(user.id)
        assert task_event["extendedProps"]["project_title"] == project.title

        # 3. Test filtering by project
        response = authenticated_client.get(
            reverse("web:calendar_events") + f"?project={project.id}"
        )
        events = response.json()
        assert len(events) >= 1  # At least the scheduled task

        # 4. Test date range filtering
        start_date = (now + timedelta(days=2)).isoformat()
        end_date = (now + timedelta(days=10)).isoformat()

        response = authenticated_client.get(
            reverse("web:calendar_events") + f"?start={start_date}&end={end_date}"
        )
        events = response.json()

        # Should not include our scheduled task (which is tomorrow)
        scheduled_events = [e for e in events if e.get("extendedProps", {}).get("task_title") == "Scheduled Task"]
        assert len(scheduled_events) == 0