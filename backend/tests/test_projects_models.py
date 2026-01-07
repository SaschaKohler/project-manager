"""
Tests for project models (Project, Task, TaskTimeEntry, etc.).
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from apps.projects.models import (
    Project, Task, TaskTimeEntry, TaskLink, TaskLabel, 
    TaskLabelAssignment, TaskAutomationRule, TaskAutomationAction,
    TaskAutomationLog, TaskButton, TaskButtonAction, Event
)


class TestProject:
    """Test cases for Project model."""
    
    def test_create_project(self, project_factory):
        """Test creating a basic project."""
        project = project_factory()
        
        assert project.title == "Test Project"
        assert project.status == Project.Status.PLANNED
        assert project.category == Project.Category.WORKSHOP
        assert project.priority == Project.Priority.MEDIUM
        assert project.color == Project.Color.INDIGO
        assert str(project) == "Test Project"
    
    def test_project_status_choices(self, project_factory):
        """Test different project statuses."""
        for status_choice in Project.Status:
            project = project_factory(status=status_choice)
            assert project.status == status_choice
    
    def test_project_category_choices(self, project_factory):
        """Test different project categories."""
        for category_choice in Project.Category:
            project = project_factory(category=category_choice)
            assert project.category == category_choice
    
    def test_project_priority_choices(self, project_factory):
        """Test different project priorities."""
        for priority_choice in Project.Priority:
            project = project_factory(priority=priority_choice)
            assert project.priority == priority_choice
    
    def test_project_color_choices(self, project_factory):
        """Test different project colors."""
        for color_choice in Project.Color:
            project = project_factory(color=color_choice)
            assert project.color == color_choice
    
    def test_project_end_days_left(self, project_factory):
        """Test the end_days_left property."""
        # Future project
        future_project = project_factory(
            end_date=timezone.now() + timedelta(days=5)
        )
        assert future_project.end_days_left == 5
        
        # Past project
        past_project = project_factory(
            end_date=timezone.now() - timedelta(days=3)
        )
        assert past_project.end_days_left == -3
    
    def test_project_str_representation(self, project_factory):
        """Test string representation of project."""
        project = project_factory(title="My Awesome Project")
        assert str(project) == "My Awesome Project"


class TestTask:
    """Test cases for Task model."""
    
    def test_create_task(self, task_factory):
        """Test creating a basic task."""
        task = task_factory()
        
        assert task.title == "Test Task"
        assert task.status == Task.Status.TODO
        assert task.priority == Task.Priority.MEDIUM
        assert task.progress == 0
        assert task.tracked_seconds == 0
        assert task.is_archived is False
        assert str(task) == "Test Task"
    
    def test_task_status_choices(self, task_factory):
        """Test different task statuses."""
        for status_choice in Task.Status:
            task = task_factory(status=status_choice)
            assert task.status == status_choice
    
    def test_task_priority_choices(self, task_factory):
        """Test different task priorities."""
        for priority_choice in Task.Priority:
            task = task_factory(priority=priority_choice)
            assert task.priority == priority_choice
    
    def test_task_time_tracking(self, task_factory):
        """Test task time tracking functionality."""
        task = task_factory(tracked_seconds=3661)  # 1 hour, 1 minute, 1 second
        
        assert task.tracked_human == "1h 01m"
        
        # Test with less than an hour
        task.tracked_seconds = 3000  # 50 minutes
        assert task.tracked_human == "50m"
    
    def test_task_ordering(self, task_factory, project_factory):
        """Test that tasks are ordered by sort_order."""
        project = project_factory()
        
        task1 = task_factory(project=project, sort_order=2)
        task2 = task_factory(project=project, sort_order=1)
        task3 = task_factory(project=project, sort_order=3)
        
        tasks = list(Task.objects.filter(project=project))
        assert tasks[0] == task2  # sort_order=1
        assert tasks[1] == task1  # sort_order=2
        assert tasks[2] == task3  # sort_order=3
    
    def test_task_str_representation(self, task_factory):
        """Test string representation of task."""
        task = task_factory(title="Fix Bug #123")
        assert str(task) == "Fix Bug #123"


class TestTaskTimeEntry:
    """Test cases for TaskTimeEntry model."""
    
    def test_create_time_entry(self, task_factory, user_factory):
        """Test creating a time entry."""
        task = task_factory()
        user = user_factory()
        
        time_entry = TaskTimeEntry.objects.create(
            task=task,
            user=user,
            started_at=timezone.now(),
            duration_seconds=3600
        )
        
        assert time_entry.task == task
        assert time_entry.user == user
        assert time_entry.duration_seconds == 3600
        assert str(time_entry) == f"{task.id} · {user.id} · {time_entry.started_at}"
    
    def test_time_entry_ordering(self, task_factory, user_factory):
        """Test that time entries are ordered by started_at desc."""
        task = task_factory()
        user = user_factory()
        
        now = timezone.now()
        
        entry1 = TaskTimeEntry.objects.create(
            task=task,
            user=user,
            started_at=now - timedelta(hours=2)
        )
        entry2 = TaskTimeEntry.objects.create(
            task=task,
            user=user,
            started_at=now - timedelta(hours=1)
        )
        entry3 = TaskTimeEntry.objects.create(
            task=task,
            user=user,
            started_at=now
        )
        
        entries = list(TaskTimeEntry.objects.all())
        assert entries[0] == entry3  # Most recent first
        assert entries[1] == entry2
        assert entries[2] == entry1


class TestTaskLabel:
    """Test cases for TaskLabel model."""
    
    def test_create_task_label(self, organization_factory):
        """Test creating a task label."""
        org = organization_factory()
        
        label = TaskLabel.objects.create(
            organization=org,
            name="Bug",
            color="red"
        )
        
        assert label.organization == org
        assert label.name == "Bug"
        assert label.color == "red"
        assert str(label) == "Bug"
    
    def test_label_unique_per_organization(self, db, organization_factory):
        """Test that labels must be unique per organization."""
        import uuid
        label_name = f"Test Label {uuid.uuid4().hex[:8]}"
        org = organization_factory()

        TaskLabel.objects.create(
            organization=org,
            name=label_name,
            color="blue"
        )

        # Creating duplicate should fail
        with pytest.raises(Exception):  # IntegrityError
            TaskLabel.objects.create(
                organization=org,
                name=label_name,
                color="red"
            )

        # But different organization can have same name
        org2 = organization_factory(name="Org 2", slug="org-2")
        TaskLabel.objects.create(
            organization=org2,
            name=label_name,
            color="green"
        )  # Should not raise


class TestTaskLabelAssignment:
    """Test cases for TaskLabelAssignment model."""
    
    def test_create_label_assignment(self, task_factory, organization_factory):
        """Test assigning a label to a task."""
        org = organization_factory()
        task = task_factory()
        
        label = TaskLabel.objects.create(
            organization=org,
            name="High Priority",
            color="red"
        )
        
        assignment = TaskLabelAssignment.objects.create(
            task=task,
            label=label
        )
        
        assert assignment.task == task
        assert assignment.label == label
        assert assignment.pk is not None
    
    def test_unique_task_label_assignment(self, db, task_factory, organization_factory):
        """Test that a task can't have the same label twice."""
        org = organization_factory()
        task = task_factory()
        
        label = TaskLabel.objects.create(
            organization=org,
            name="Bug",
            color="red"
        )
        
        # First assignment
        TaskLabelAssignment.objects.create(task=task, label=label)
        
        # Second assignment should fail
        with pytest.raises(Exception):  # IntegrityError
            TaskLabelAssignment.objects.create(task=task, label=label)


class TestTaskAutomationRule:
    """Test cases for TaskAutomationRule model."""
    
    def test_create_automation_rule(self, automation_rule_factory):
        """Test creating an automation rule."""
        rule = automation_rule_factory(
            name="Auto-assign new tasks",
            trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED
        )
        
        assert rule.name == "Auto-assign new tasks"
        assert rule.trigger_type == TaskAutomationRule.TriggerType.TASK_CREATED
        assert rule.is_active is True
        assert str(rule) == "Auto-assign new tasks (Task Created)"
    
    def test_automation_trigger_types(self, automation_rule_factory):
        """Test different automation trigger types."""
        for trigger_choice in TaskAutomationRule.TriggerType:
            rule = automation_rule_factory(trigger_type=trigger_choice)
            assert rule.trigger_type == trigger_choice
    
    def test_rule_ordering(self, automation_rule_factory):
        """Test that rules are ordered by created_at desc."""
        rule1 = automation_rule_factory()
        rule2 = automation_rule_factory()
        rule3 = automation_rule_factory()
        
        rules = list(TaskAutomationRule.objects.all())
        assert rules[0] == rule3  # Most recent first
        assert rules[1] == rule2
        assert rules[2] == rule1


class TestTaskAutomationAction:
    """Test cases for TaskAutomationAction model."""
    
    def test_create_automation_action(self, automation_rule_factory):
        """Test creating an automation action."""
        rule = automation_rule_factory()
        
        action = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.CHANGE_STATUS,
            action_config={"status": Task.Status.IN_PROGRESS},
            sort_order=1
        )
        
        assert action.rule == rule
        assert action.action_type == TaskAutomationAction.ActionType.CHANGE_STATUS
        assert action.action_config == {"status": Task.Status.IN_PROGRESS}
        assert action.sort_order == 1
        assert str(action) == "Change Status"
    
    def test_action_types(self, automation_rule_factory):
        """Test different automation action types."""
        rule = automation_rule_factory()
        
        for action_choice in TaskAutomationAction.ActionType:
            action = TaskAutomationAction.objects.create(
                rule=rule,
                action_type=action_choice
            )
            assert action.action_type == action_choice
    
    def test_action_ordering(self, automation_rule_factory):
        """Test that actions are ordered by sort_order."""
        rule = automation_rule_factory()
        
        action1 = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.CHANGE_STATUS,
            sort_order=2
        )
        action2 = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.SET_PRIORITY,
            sort_order=1
        )
        action3 = TaskAutomationAction.objects.create(
            rule=rule,
            action_type=TaskAutomationAction.ActionType.ASSIGN_USER,
            sort_order=3
        )
        
        actions = list(TaskAutomationAction.objects.filter(rule=rule))
        assert actions[0] == action2  # sort_order=1
        assert actions[1] == action1  # sort_order=2
        assert actions[2] == action3  # sort_order=3


class TestTaskAutomationLog:
    """Test cases for TaskAutomationLog model."""
    
    def test_create_automation_log(self, automation_rule_factory, task_factory):
        """Test creating an automation log entry."""
        rule = automation_rule_factory()
        task = task_factory()
        
        log = TaskAutomationLog.objects.create(
            rule=rule,
            task=task,
            status=TaskAutomationLog.Status.SUCCESS,
            message="Rule executed successfully"
        )
        
        assert log.rule == rule
        assert log.task == task
        assert log.status == TaskAutomationLog.Status.SUCCESS
        assert log.message == "Rule executed successfully"
    
    def test_log_status_choices(self, automation_rule_factory, task_factory):
        """Test different log statuses."""
        rule = automation_rule_factory()
        task = task_factory()
        
        for status_choice in TaskAutomationLog.Status:
            log = TaskAutomationLog.objects.create(
                rule=rule,
                task=task,
                status=status_choice,
                message=f"Test {status_choice.value}"
            )
            assert log.status == status_choice
    
    def test_log_ordering(self, automation_rule_factory, task_factory):
        """Test that logs are ordered by executed_at desc."""
        rule = automation_rule_factory()
        task = task_factory()
        
        now = timezone.now()
        
        log1 = TaskAutomationLog.objects.create(
            rule=rule,
            task=task,
            status=TaskAutomationLog.Status.SUCCESS,
            executed_at=now - timedelta(hours=2)
        )
        log2 = TaskAutomationLog.objects.create(
            rule=rule,
            task=task,
            status=TaskAutomationLog.Status.SUCCESS,
            executed_at=now - timedelta(hours=1)
        )
        log3 = TaskAutomationLog.objects.create(
            rule=rule,
            task=task,
            status=TaskAutomationLog.Status.SUCCESS,
            executed_at=now
        )
        
        logs = list(TaskAutomationLog.objects.all())
        assert logs[0] == log3  # Most recent first
        assert logs[1] == log2
        assert logs[2] == log1


class TestTaskButton:
    """Test cases for TaskButton model."""
    
    def test_create_task_button(self, organization_factory, user_factory):
        """Test creating a task button."""
        org = organization_factory()
        user = user_factory()
        
        button = TaskButton.objects.create(
            organization=org,
            name="Start Timer",
            icon="play",
            color="green",
            created_by=user
        )
        
        assert button.organization == org
        assert button.name == "Start Timer"
        assert button.icon == "play"
        assert button.color == "green"
        assert button.is_active is True
        assert button.show_on_status == []
        assert button.show_on_priority == []
        assert str(button) == "Start Timer"
    
    def test_button_should_show_for_task(self, organization_factory, user_factory, task_factory):
        """Test the should_show_for_task method."""
        org = organization_factory()
        user = user_factory()
        task = task_factory()
        
        # Create a label for testing
        label = TaskLabel.objects.create(
            organization=org,
            name="Ready",
            color="green"
        )
        
        # Button that shows on specific status
        status_button = TaskButton.objects.create(
            organization=org,
            name="In Progress Button",
            show_on_status=[Task.Status.IN_PROGRESS],
            created_by=user
        )
        
        # Should not show for TODO task
        assert status_button.should_show_for_task(task) is False
        
        # Change task status and test again
        task.status = Task.Status.IN_PROGRESS
        task.save()
        assert status_button.should_show_for_task(task) is True
        
        # Button with required label
        label_button = TaskButton.objects.create(
            organization=org,
            name="Label Button",
            show_when_has_label=label,
            created_by=user
        )
        
        # Should not show without label
        assert label_button.should_show_for_task(task) is False
        
        # Add label to task
        TaskLabelAssignment.objects.create(task=task, label=label)
        assert label_button.should_show_for_task(task) is True


class TestEvent:
    """Test cases for Event model."""
    
    def test_create_event(self, project_factory):
        """Test creating an event."""
        project = project_factory()
        
        event = Event.objects.create(
            project=project,
            title="Team Meeting",
            description="Weekly team sync",
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            location="Conference Room A",
            type=Event.Type.MEETING
        )
        
        assert event.project == project
        assert event.title == "Team Meeting"
        assert event.description == "Weekly team sync"
        assert event.type == Event.Type.MEETING
        assert event.location == "Conference Room A"
        assert str(event) == "Team Meeting"
    
    def test_event_type_choices(self, project_factory):
        """Test different event types."""
        project = project_factory()
        
        for type_choice in Event.Type:
            event = Event.objects.create(
                project=project,
                title=f"Test {type_choice.value}",
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(hours=1),
                type=type_choice
            )
            assert event.type == type_choice