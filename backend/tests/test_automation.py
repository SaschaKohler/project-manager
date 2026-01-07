"""
Tests for automation functionality.
"""

import pytest
from unittest.mock import patch, Mock
from django.utils import timezone
from datetime import timedelta

from apps.projects.automation import TaskAutomationEngine, execute_task_button
from apps.projects.models import (
    Task, TaskAutomationRule, TaskAutomationAction, TaskAutomationLog,
    TaskLabel, TaskLabelAssignment
)


class TestTaskAutomationEngine:
    """Test cases for TaskAutomationEngine."""
    
    @pytest.fixture
    def automation_engine(self, user_factory):
        """Create automation engine with test user."""
        user = user_factory()
        return TaskAutomationEngine(triggered_by=user)
    
    @pytest.fixture
    def complete_setup(self, db, organization_factory, user_factory, project_factory):
        """Create complete setup for automation testing."""
        org = organization_factory()
        user = user_factory()
        project = project_factory(created_by=user)
        
        # Create some tasks
        task1 = Task.objects.create(
            project=project,
            title="Task 1",
            status=Task.Status.TODO,
            priority=Task.Priority.MEDIUM,
            assigned_to=user
        )
        
        task2 = Task.objects.create(
            project=project,
            title="Task 2", 
            status=Task.Status.IN_PROGRESS,
            priority=Task.Priority.HIGH,
            assigned_to=user
        )
        
        # Create a label
        label = TaskLabel.objects.create(
            organization=org,
            name="Urgent",
            color="red"
        )
        
        return {
            "org": org,
            "user": user,
            "project": project,
            "task1": task1,
            "task2": task2,
            "label": label
        }
    
    def test_trigger_task_created(self, automation_engine, complete_setup):
        """Test triggering task creation automation."""
        task = complete_setup["task1"]
        
        # Create automation rule
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Auto-assign new tasks",
            trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
            is_active=True
        )
        
        # Create action to change status
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.CHANGE_STATUS,
            action_config={"status": Task.Status.IN_PROGRESS}
        )
        
        # Trigger automation
        logs = automation_engine.trigger_task_created(task)
        
        # Verify results
        assert len(logs) == 1
        assert logs[0].status == TaskAutomationLog.Status.SUCCESS
        assert logs[0].rule == rule
        assert logs[0].task == task
        
        # Check that task was updated
        task.refresh_from_db()
        assert task.status == Task.Status.IN_PROGRESS
    
    def test_trigger_status_changed(self, automation_engine, complete_setup):
        """Test triggering status change automation."""
        task = complete_setup["task1"]
        
        # Create rule with status filter
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Set high priority when moving to in progress",
            trigger_type=TaskAutomationRule.TriggerType.STATUS_CHANGED,
            trigger_config={"to_status": Task.Status.IN_PROGRESS},
            is_active=True
        )
        
        # Create action to set priority
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.SET_PRIORITY,
            action_config={"priority": Task.Priority.HIGH}
        )
        
        # Change task status
        old_status = task.status
        task.status = Task.Status.IN_PROGRESS
        task.save()
        
        # Trigger automation
        logs = automation_engine.trigger_status_changed(task, old_status, task.status)
        
        # Verify results
        assert len(logs) == 1
        assert logs[0].status == TaskAutomationLog.Status.SUCCESS
        
        # Check that priority was updated
        task.refresh_from_db()
        assert task.priority == Task.Priority.HIGH
    
    def test_trigger_status_changed_no_match(self, automation_engine, complete_setup):
        """Test that status change automation respects filters."""
        task = complete_setup["task1"]
        
        # Create rule that only triggers on specific status change
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Only from TODO to IN_PROGRESS",
            trigger_type=TaskAutomationRule.TriggerType.STATUS_CHANGED,
            trigger_config={
                "from_status": Task.Status.TODO,
                "to_status": Task.Status.DONE
            },
            is_active=True
        )
        
        # Create action
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.ASSIGN_USER,
            action_config={"assign_triggered_by": True}
        )
        
        # Change status but not matching the filter (TODO -> IN_PROGRESS)
        old_status = task.status
        task.status = Task.Status.IN_PROGRESS
        task.save()
        
        # Trigger automation
        logs = automation_engine.trigger_status_changed(task, old_status, task.status)
        
        # Should not trigger because filter doesn't match
        assert len(logs) == 0
    
    def test_trigger_label_added(self, automation_engine, complete_setup):
        """Test triggering label addition automation."""
        task = complete_setup["task1"]
        label = complete_setup["label"]
        
        # Create rule that triggers on specific label
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Set high priority for urgent label",
            trigger_type=TaskAutomationRule.TriggerType.LABEL_ADDED,
            trigger_config={"label_id": str(label.id)},
            is_active=True
        )
        
        # Create action
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.SET_PRIORITY,
            action_config={"priority": Task.Priority.HIGH}
        )
        
        # Add label to task
        TaskLabelAssignment.objects.create(task=task, label=label)
        
        # Trigger automation
        logs = automation_engine.trigger_label_added(task, label)
        
        # Verify results
        assert len(logs) == 1
        assert logs[0].status == TaskAutomationLog.Status.SUCCESS
        
        # Check that priority was updated
        task.refresh_from_db()
        assert task.priority == Task.Priority.HIGH
    
    def test_trigger_due_date_approaching(self, automation_engine, complete_setup):
        """Test triggering due date approaching automation."""
        task = complete_setup["task1"]
        
        # Set due date for 3 days from now
        task.due_date = timezone.now() + timedelta(days=3)
        task.save()
        
        # Create rule that triggers 3 days before due date
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Remind 3 days before due",
            trigger_type=TaskAutomationRule.TriggerType.DUE_DATE_APPROACHING,
            trigger_config={"days_before": 3},
            is_active=True
        )
        
        # Create action
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.SEND_NOTIFICATION,
            action_config={"message": "Task is due in 3 days!"}
        )
        
        # Trigger automation
        logs = automation_engine.trigger_due_date_approaching(task, 3)
        
        # Verify results
        assert len(logs) == 1
        assert logs[0].status == TaskAutomationLog.Status.SUCCESS
    
    def test_automation_action_change_status(self, automation_engine, complete_setup):
        """Test changing task status via automation."""
        task = complete_setup["task1"]
        
        # Create action
        action = TaskAutomationAction(
            action_type=TaskAutomationAction.ActionType.CHANGE_STATUS,
            action_config={"status": Task.Status.DONE}
        )
        
        # Execute action
        automation_engine._execute_action(action, task)
        
        # Check result
        task.refresh_from_db()
        assert task.status == Task.Status.DONE
    
    def test_automation_action_set_priority(self, automation_engine, complete_setup):
        """Test setting task priority via automation."""
        task = complete_setup["task1"]
        
        # Create action
        action = TaskAutomationAction(
            action_type=TaskAutomationAction.ActionType.SET_PRIORITY,
            action_config={"priority": Task.Priority.HIGH}
        )
        
        # Execute action
        automation_engine._execute_action(action, task)
        
        # Check result
        task.refresh_from_db()
        assert task.priority == Task.Priority.HIGH
    
    def test_automation_action_add_label(self, automation_engine, complete_setup):
        """Test adding label via automation."""
        task = complete_setup["task1"]
        label = complete_setup["label"]
        
        # Create action
        action = TaskAutomationAction(
            action_type=TaskAutomationAction.ActionType.ADD_LABEL,
            action_config={"label_id": str(label.id)}
        )
        
        # Execute action
        automation_engine._execute_action(action, task)
        
        # Check result
        assert TaskLabelAssignment.objects.filter(task=task, label=label).exists()
    
    def test_automation_action_remove_label(self, automation_engine, complete_setup):
        """Test removing label via automation."""
        task = complete_setup["task1"]
        label = complete_setup["label"]
        
        # First add the label
        TaskLabelAssignment.objects.create(task=task, label=label)
        
        # Create action to remove it
        action = TaskAutomationAction(
            action_type=TaskAutomationAction.ActionType.REMOVE_LABEL,
            action_config={"label_id": str(label.id)}
        )
        
        # Execute action
        automation_engine._execute_action(action, task)
        
        # Check result
        assert not TaskLabelAssignment.objects.filter(task=task, label=label).exists()
    
    def test_automation_action_set_due_date(self, automation_engine, complete_setup):
        """Test setting due date via automation."""
        task = complete_setup["task1"]
        
        # Create action
        action = TaskAutomationAction(
            action_type=TaskAutomationAction.ActionType.SET_DUE_DATE,
            action_config={"days_offset": 7}
        )
        
        # Execute action
        automation_engine._execute_action(action, task)
        
        # Check result
        task.refresh_from_db()
        expected_date = timezone.now() + timedelta(days=7)
        assert abs((task.due_date - expected_date).total_seconds()) < 60  # Within 1 minute
    
    def test_automation_action_archive_task(self, automation_engine, complete_setup):
        """Test archiving task via automation."""
        task = complete_setup["task1"]
        
        # Create action
        action = TaskAutomationAction(
            action_type=TaskAutomationAction.ActionType.ARCHIVE_TASK
        )
        
        # Execute action
        automation_engine._execute_action(action, task)
        
        # Check result
        task.refresh_from_db()
        assert task.is_archived is True
        assert task.archived_at is not None
        assert task.archived_by == automation_engine.triggered_by
    
    def test_automation_failure_handling(self, automation_engine, complete_setup):
        """Test that automation failures are properly logged."""
        task = complete_setup["task1"]
        
        # Create rule
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Failing rule",
            trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
            is_active=True
        )
        
        # Create action that will fail (invalid status)
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.CHANGE_STATUS,
            action_config={"status": "INVALID_STATUS"}
        )
        
        # Trigger automation
        logs = automation_engine.trigger_task_created(task)
        
        # Should have one failed log
        assert len(logs) == 1
        assert logs[0].status == TaskAutomationLog.Status.FAILED
        assert "INVALID_STATUS" in logs[0].message
    
    def test_project_specific_rules(self, automation_engine, complete_setup):
        """Test that rules can be project-specific."""
        task = complete_setup["task1"]
        
        # Create organization-wide rule
        org_rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Org-wide rule",
            trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
            is_active=True
        )
        
        # Create project-specific rule
        project_rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            project=complete_setup["project"],
            name="Project-specific rule",
            trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
            is_active=True
        )
        
        # Both rules should trigger
        logs = automation_engine.trigger_task_created(task)
        assert len(logs) == 2
        
        # Verify both rules are in logs
        rule_ids = {log.rule.id for log in logs}
        assert org_rule.id in rule_ids
        assert project_rule.id in rule_ids
    
    def test_inactive_rules_ignored(self, automation_engine, complete_setup):
        """Test that inactive rules are ignored."""
        task = complete_setup["task1"]
        
        # Create inactive rule
        rule = TaskAutomationRule.objects.create(
            organization=complete_setup["org"],
            created_by=complete_setup["user"],
            name="Inactive rule",
            trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
            is_active=False  # Inactive
        )
        
        # Should not trigger
        logs = automation_engine.trigger_task_created(task)
        assert len(logs) == 0


class TestExecuteTaskButton:
    """Test cases for execute_task_button function."""
    
    def test_execute_task_button_success(self, db, user_factory, task_factory):
        """Test successful task button execution."""
        from apps.projects.models import TaskButton, TaskButtonAction
        
        # Setup
        org_factory = user_factory  # Reuse fixture
        org = org_factory()
        user = user_factory()
        task = task_factory()
        
        # Create button
        button = TaskButton.objects.create(
            organization=org,
            name="Complete Task",
            created_by=user
        )
        
        # Create button action
        button_action = TaskButtonAction.objects.create(
            button=button,
            action_type=TaskAutomationAction.ActionType.CHANGE_STATUS,
            action_config={"status": Task.Status.DONE}
        )
        
        # Execute button
        result = execute_task_button(str(button.id), task, user)
        
        # Verify success
        assert result is True
        task.refresh_from_db()
        assert task.status == Task.Status.DONE
    
    def test_execute_task_button_wrong_org(self, db, user_factory, task_factory):
        """Test that buttons from wrong organization are rejected."""
        from apps.projects.models import TaskButton
        
        # Setup with different organizations
        user = user_factory()
        task = task_factory()
        
        # Create button for different organization
        other_org = user_factory()  # This creates a user, not org
        # We need to properly create an organization
        from apps.tenants.models import Organization
        other_org_obj = Organization.objects.create(name="Other Org", slug="other-org")
        
        button = TaskButton.objects.create(
            organization=other_org_obj,
            name="Wrong Org Button",
            created_by=user
        )
        
        # Execute button should fail
        result = execute_task_button(str(button.id), task, user)
        assert result is False
    
    def test_execute_task_button_not_found(self, db, user_factory, task_factory):
        """Test execution of non-existent button."""
        user = user_factory()
        task = task_factory()
        
        # Try to execute non-existent button
        result = execute_task_button("non-existent-id", task, user)
        assert result is False
    
    def test_execute_task_button_inactive(self, db, user_factory, task_factory):
        """Test that inactive buttons are not executed."""
        from apps.projects.models import TaskButton
        
        # Setup
        user = user_factory()
        task = task_factory()
        org = task.project.organization
        
        # Create inactive button
        button = TaskButton.objects.create(
            organization=org,
            name="Inactive Button",
            is_active=False,  # Inactive
            created_by=user
        )
        
        # Execute button should fail
        result = execute_task_button(str(button.id), task, user)
        assert result is False