"""
Tests for REST API endpoints.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.projects.models import Project, Task
from apps.tenants.models import Organization


class TestOrganizationAPI:
    """Test cases for Organization API endpoints."""

    def test_list_organizations(self, authenticated_api_client, organization_factory):
        """Test listing organizations."""
        api_client, user = authenticated_api_client
        org1 = organization_factory(name="Org 1", user=user)
        org2 = organization_factory(name="Org 2", user=user)

        response = api_client.get(reverse("org-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_create_organization(self, authenticated_api_client, user_factory):
        """Test creating an organization."""
        api_client, user = authenticated_api_client

        data = {
            "name": "New Organization",
            "slug": "new-org"
        }

        response = api_client.post(reverse("org-list"), data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Organization"
        assert response.data["slug"] == "new-org"

    def test_retrieve_organization(self, authenticated_api_client, organization_factory):
        """Test retrieving a single organization."""
        api_client, user = authenticated_api_client
        org = organization_factory(user=user)

        response = api_client.get(
            reverse("org-detail", kwargs={"pk": org.id})
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(org.id)
        assert response.data["name"] == org.name


class TestProjectAPI:
    """Test cases for Project API endpoints."""

    def test_list_projects(self, authenticated_api_client_with_org, project_factory):
        """Test listing projects."""
        api_client, org = authenticated_api_client_with_org
        project1 = project_factory(organization=org)
        project2 = project_factory(organization=org, title="Project 2")

        response = api_client.get(reverse("project-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_create_project(self, authenticated_api_client_with_org, user_factory):
        """Test creating a project."""
        api_client, org = authenticated_api_client_with_org
        user = user_factory()

        data = {
            "title": "New Project",
            "description": "Project description",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "category": "WORKSHOP",
            "priority": "MEDIUM",
            "color": "indigo"
        }

        response = api_client.post(reverse("project-list"), data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Project"
        assert str(response.data["organization"]) == str(org.id)

    def test_retrieve_project(self, authenticated_api_client_with_org, project_factory):
        """Test retrieving a single project."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)

        response = api_client.get(
            reverse("project-detail", kwargs={"pk": project.id})
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(project.id)
        assert response.data["title"] == project.title

    def test_update_project(self, authenticated_api_client_with_org, project_factory):
        """Test updating a project."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)

        data = {
            "title": "Updated Project Title",
            "description": project.description or "",
            "start_date": project.start_date.isoformat(),
            "end_date": project.end_date.isoformat(),
            "category": project.category,
            "priority": project.priority,
            "color": project.color
        }

        response = api_client.put(
            reverse("project-detail", kwargs={"pk": project.id}),
            data
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Project Title"

    def test_delete_project(self, authenticated_api_client_with_org, project_factory):
        """Test deleting a project."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)

        response = api_client.delete(
            reverse("project-detail", kwargs={"pk": project.id})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Project.objects.filter(id=project.id).exists()


class TestTaskAPI:
    """Test cases for Task API endpoints."""

    def test_list_tasks(self, authenticated_api_client_with_org, task_factory, project_factory):
        """Test listing tasks."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)
        task1 = task_factory(project=project)
        task2 = task_factory(project=project, title="Task 2")

        response = api_client.get(reverse("task-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_create_task(self, authenticated_api_client_with_org, project_factory, user_factory):
        """Test creating a task."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)
        user = user_factory()

        data = {
            "project": str(project.id),
            "title": "New Task",
            "description": "Task description",
            "status": "TODO",
            "priority": "MEDIUM",
            "assigned_to": str(user.id)
        }

        response = api_client.post(reverse("task-list"), data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Task"
        assert str(response.data["project"]) == str(project.id)

    def test_retrieve_task(self, authenticated_api_client_with_org, task_factory, project_factory):
        """Test retrieving a single task."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)
        task = task_factory(project=project)

        response = api_client.get(
            reverse("task-detail", kwargs={"pk": task.id})
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(task.id)
        assert response.data["title"] == task.title

    def test_update_task(self, authenticated_api_client_with_org, task_factory, project_factory):
        """Test updating a task."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)
        task = task_factory(project=project)

        data = {
            "project": str(task.project.id),
            "title": "Updated Task Title",
            "description": task.description or "",
            "status": task.status,
            "priority": task.priority,
            "assigned_to": str(task.assigned_to.id)
        }

        response = api_client.put(
            reverse("task-detail", kwargs={"pk": task.id}),
            data
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Task Title"

    def test_delete_task(self, authenticated_api_client_with_org, task_factory, project_factory):
        """Test deleting a task."""
        api_client, org = authenticated_api_client_with_org
        project = project_factory(organization=org)
        task = task_factory(project=project)

        response = api_client.delete(
            reverse("task-detail", kwargs={"pk": task.id})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Task.objects.filter(id=task.id).exists()


class TestAuthenticationAPI:
    """Test cases for authentication API endpoints."""

    def test_token_obtain_pair(self, client, user_factory):
        """Test obtaining JWT token pair."""
        user = user_factory()

        data = {
            "email": user.email,
            "password": "testpass123"
        }

        response = client.post(reverse("token_obtain_pair"), data)

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_token_refresh(self, client, user_factory):
        """Test refreshing JWT token."""
        user = user_factory()

        # First get tokens
        data = {
            "email": user.email,
            "password": "testpass123"
        }

        response = client.post(reverse("token_obtain_pair"), data)
        refresh_token = response.data["refresh"]

        # Now refresh
        refresh_data = {
            "refresh": refresh_token
        }

        response = client.post(reverse("token_refresh"), refresh_data)

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    @pytest.mark.django_db
    def test_register_user(self, client):
        """Test user registration."""
        data = {
            "email": "newuser@example.com",
            "password": "newpass123",
            "name": "New User"
        }

        response = client.post(reverse("api_register"), data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "newuser@example.com"

    def test_unauthenticated_access(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.get(reverse("project-list"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED