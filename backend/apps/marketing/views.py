from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from typing import Optional

from apps.tenants.tenancy import require_membership, resolve_organization_from_request
from apps.tenants.models import Organization

from .models import MarketingCampaign, MarketingTask
from .serializers import MarketingCampaignSerializer, MarketingTaskSerializer


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    _organization: Optional[Organization] = None

    @property
    def organization(self) -> Organization:
        if self._organization is None:
            raise RuntimeError("Organization not set")
        return self._organization

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        org = resolve_organization_from_request(request)
        if org is None:
            raise ValidationError(
                {
                    "org": "Missing or invalid organization. Provide X-Org-Id header or ?org=<uuid>"
                }
            )
        require_membership(request, org)
        self._organization = org
        setattr(request, "organization", org)


class MarketingCampaignViewSet(OrganizationScopedViewSet):
    serializer_class = MarketingCampaignSerializer

    def get_queryset(self):
        return MarketingCampaign.objects.filter(organization=self.organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.organization)


class MarketingTaskViewSet(OrganizationScopedViewSet):
    serializer_class = MarketingTaskSerializer

    def get_queryset(self):
        return MarketingTask.objects.filter(
            organization=self.organization
        ).select_related("assigned_to", "campaign")

    def perform_create(self, serializer):
        campaign = serializer.validated_data.get("campaign")
        if campaign is not None and campaign.organization_id != self.organization.id:
            raise ValidationError({"campaign": "Campaign is not in this organization"})
        serializer.save(organization=self.organization)
