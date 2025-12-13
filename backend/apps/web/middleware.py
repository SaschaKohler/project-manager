from apps.tenants.models import Membership, Organization


class ActiveOrganizationMiddleware:
    session_key = "active_org_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_org = None

        if request.user.is_authenticated:
            org_id = request.session.get(self.session_key)
            org = None
            if org_id:
                try:
                    org = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    org = None

            if org is not None:
                if Membership.objects.filter(user=request.user, organization=org).exists():
                    request.active_org = org

            if request.active_org is None:
                membership = (
                    Membership.objects.filter(user=request.user)
                    .select_related("organization")
                    .order_by("created_at")
                    .first()
                )
                if membership:
                    request.active_org = membership.organization
                    request.session[self.session_key] = str(membership.organization_id)

        return self.get_response(request)
