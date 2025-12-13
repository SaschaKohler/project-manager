from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.tenants.tenancy import require_membership, resolve_organization_from_request

from .models import MarketingCampaign, MarketingTask
from .serializers import MarketingCampaignSerializer, MarketingTaskSerializer


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        org = resolve_organization_from_request(request)
        if org is None:
            raise ValidationError({"org": "Missing or invalid organization. Provide X-Org-Id header or ?org=<uuid>"})
        require_membership(request, org)
        request.organization = org


class MarketingCampaignViewSet(OrganizationScopedViewSet):
    serializer_class = MarketingCampaignSerializer

    def get_queryset(self):
        return MarketingCampaign.objects.filter(organization=self.request.organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class MarketingTaskViewSet(OrganizationScopedViewSet):
    serializer_class = MarketingTaskSerializer

    def get_queryset(self):
        return MarketingTask.objects.filter(organization=self.request.organization).select_related("assigned_to", "campaign")

    def perform_create(self, serializer):
        campaign = serializer.validated_data.get("campaign")
        if campaign is not None and campaign.organization_id != self.request.organization.id:
            raise ValidationError({"campaign": "Campaign is not in this organization"})
        serializer.save(organization=self.request.organization)
