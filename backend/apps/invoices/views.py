from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.tenants.tenancy import require_membership, resolve_organization_from_request
from apps.tenants.models import Organization

from .models import Invoice, InvoiceItem
from .serializers import InvoiceSerializer, InvoiceItemSerializer


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    _organization: Organization | None = None

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


class InvoiceViewSet(OrganizationScopedViewSet):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(organization=self.organization).select_related(
            "organization", "created_by"
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.organization, created_by=self.request.user)


class InvoiceItemViewSet(OrganizationScopedViewSet):
    serializer_class = InvoiceItemSerializer

    def get_queryset(self):
        return InvoiceItem.objects.filter(
            invoice__organization=self.organization
        ).select_related("invoice")

    def perform_create(self, serializer):
        invoice = serializer.validated_data["invoice"]
        if invoice.organization_id != self.organization.id:
            raise ValidationError({"invoice": "Invoice is not in this organization"})
        serializer.save()