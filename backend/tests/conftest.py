"""
Pytest configuration and shared fixtures.
"""

import os
import sys
from pathlib import Path

import pytest
from django.conf import settings

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Configure Django settings for testing
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Initialize Django
import django
django.setup()


@pytest.fixture
def client():
    """Django test client."""
    from django.test import Client
    return Client()


@pytest.fixture
def api_client():
    """Django REST framework test client with authentication."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def user_factory(db):
    """Factory for creating test users."""
    from django.contrib.auth import get_user_model
    import uuid
    
    def create_user(email=None, password="testpass123", **kwargs):
        User = get_user_model()
        if email is None:
            email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        return User.objects.create_user(
            email=email,
            password=password,
            **kwargs
        )
    
    return create_user


@pytest.fixture
def organization_factory(db, user_factory):
    """Factory for creating test organizations."""
    from apps.tenants.models import Organization, Membership
    import uuid

    def create_organization(name="Test Org", slug=None, user=None):
        if user is None:
            user = user_factory()
        if slug is None:
            slug = f"test-org-{uuid.uuid4().hex[:8]}"

        org = Organization.objects.create(name=name, slug=slug)
        Membership.objects.create(
            organization=org,
            user=user,
            role=Membership.Role.OWNER
        )
        return org

    return create_organization


@pytest.fixture
def project_factory(db, organization_factory, user_factory):
    """Factory for creating test projects."""
    from apps.projects.models import Project
    from datetime import datetime

    def create_project(organization=None, created_by=None, **kwargs):
        if organization is None:
            organization = organization_factory()
        if created_by is None:
            created_by = user_factory()

        defaults = {
            "title": "Test Project",
            "start_date": datetime(2024, 1, 1, 0, 0, 0),
            "end_date": datetime(2024, 12, 31, 23, 59, 59),
            "category": Project.Category.WORKSHOP,
        }
        defaults.update(kwargs)

        return Project.objects.create(
            organization=organization,
            created_by=created_by,
            **defaults
        )

    return create_project


@pytest.fixture
def task_factory(db, project_factory, user_factory):
    """Factory for creating test tasks."""
    from apps.projects.models import Task
    
    def create_task(project=None, assigned_to=None, **kwargs):
        if project is None:
            project = project_factory()
        if assigned_to is None:
            assigned_to = user_factory()
        
        defaults = {
            "title": "Test Task",
            "status": Task.Status.TODO,
            "priority": Task.Priority.MEDIUM,
        }
        defaults.update(kwargs)
        
        return Task.objects.create(
            project=project,
            assigned_to=assigned_to,
            **defaults
        )
    
    return create_task


@pytest.fixture
def automation_rule_factory(db, organization_factory, user_factory):
    """Factory for creating test automation rules."""
    from apps.projects.models import TaskAutomationRule
    
    def create_automation_rule(
        organization=None,
        created_by=None,
        trigger_type=TaskAutomationRule.TriggerType.TASK_CREATED,
        **kwargs
    ):
        if organization is None:
            organization = organization_factory()
        if created_by is None:
            created_by = user_factory()
        
        defaults = {
            "name": "Test Rule",
            "trigger_type": trigger_type,
            "is_active": True,
        }
        defaults.update(kwargs)
        
        return TaskAutomationRule.objects.create(
            organization=organization,
            created_by=created_by,
            **defaults
        )
    
    return create_automation_rule


@pytest.fixture
def authenticated_client(client, user_factory):
    """Authenticated Django test client."""
    user = user_factory()
    client.force_login(user)
    return client


@pytest.fixture
def authenticated_api_client(api_client, user_factory):
    """Authenticated REST API client."""
    user = user_factory()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.fixture
def authenticated_api_client_with_org(api_client, user_factory, organization_factory):
    """Authenticated REST API client with organization context."""
    user = user_factory()
    org = organization_factory(user=user)
    api_client.force_authenticate(user=user)
    api_client.defaults['HTTP_X_ORG_ID'] = str(org.id)
    return api_client, org


@pytest.fixture
def active_organization(authenticated_client, organization_factory):
    """Client with active organization set."""
    org = organization_factory()
    # Simulate setting active organization in session
    authenticated_client.session["active_org_id"] = str(org.id)
    return org


@pytest.fixture
def mock_ai_provider():
    """Mock AI provider for testing."""
    from unittest.mock import patch
    
    with patch("config.settings.AI_PROVIDER", "mock"):
        with patch("config.settings.ANTHROPIC_API_KEY", "test-key"):
            yield


@pytest.fixture(autouse=True)
def reset_celery_eager():
    """Ensure celery is in eager mode for testing."""
    try:
        from celery import current_app
        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propagates = True
        yield
        current_app.conf.task_always_eager = False
    except ImportError:
        # Celery not installed, skip
        yield


@pytest.fixture
def temp_media_dir(tmp_path):
    """Temporary media directory for file uploads."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    
    old_media_root = settings.MEDIA_ROOT
    settings.MEDIA_ROOT = str(media_dir)
    
    yield media_dir
    
    settings.MEDIA_ROOT = old_media_root