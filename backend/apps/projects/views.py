from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from apps.tenants.tenancy import require_membership, resolve_organization_from_request
from apps.tenants.models import Membership

from .models import Event, Project, Task
from .serializers import EventSerializer, ProjectSerializer, TaskSerializer


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        org = resolve_organization_from_request(request)
        if org is None:
            raise ValidationError({"org": "Missing or invalid organization. Provide X-Org-Id header or ?org=<uuid>"})
        require_membership(request, org)
        request.organization = org


class ProjectViewSet(OrganizationScopedViewSet):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(organization=self.request.organization).select_related("organization", "created_by")

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization, created_by=self.request.user)


class TaskViewSet(OrganizationScopedViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(project__organization=self.request.organization).select_related("project", "assigned_to")

    def _can_edit(self, task: Task) -> bool:
        membership = Membership.objects.filter(organization=self.request.organization, user=self.request.user).only("role").first()
        if membership is None:
            return False
        if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}:
            return True
        return task.assigned_to_id == self.request.user.id

    def _require_edit(self, task: Task) -> None:
        if not self._can_edit(task):
            raise PermissionDenied("You do not have permission to modify this task")

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        self._require_edit(task)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        self._require_edit(task)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        self._require_edit(task)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if project.organization_id != self.request.organization.id:
            raise ValidationError({"project": "Project is not in this organization"})
        serializer.save()


class EventViewSet(OrganizationScopedViewSet):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.filter(project__organization=self.request.organization).select_related("project")

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if project.organization_id != self.request.organization.id:
            raise ValidationError({"project": "Project is not in this organization"})
        serializer.save()
