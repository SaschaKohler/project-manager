from typing import Optional

from rest_framework.exceptions import PermissionDenied

from .models import Membership, Organization


ORG_HEADER = "HTTP_X_ORG_ID"
ORG_QUERY_PARAM = "org"


def resolve_organization_from_request(request) -> Optional[Organization]:
    org_id = request.META.get(ORG_HEADER) or request.query_params.get(ORG_QUERY_PARAM)
    if not org_id:
        return None
    try:
        return Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return None


def require_membership(request, org: Organization) -> None:
    if not Membership.objects.filter(organization=org, user=request.user).exists():
        raise PermissionDenied("Not a member of this organization")
