from rest_framework import permissions

from .models import Membership


class IsOrganizationMember(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        org = getattr(request, "organization", None)
        if org is None:
            return False
        return Membership.objects.filter(organization=org, user=request.user).exists()
