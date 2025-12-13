from django.utils.text import slugify
from rest_framework import permissions, viewsets

from .models import Membership, Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Organization.objects.filter(memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        name = serializer.validated_data.get("name")
        slug = serializer.validated_data.get("slug") or slugify(name)
        org = serializer.save(slug=slug)
        Membership.objects.create(organization=org, user=self.request.user, role=Membership.Role.OWNER)
