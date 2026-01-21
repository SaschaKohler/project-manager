from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from django.utils.translation import gettext_lazy as _

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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.organization
        return context

    def get_queryset(self):
        return Invoice.objects.filter(
            organization=self.organization,
            company__owner=self.request.user,
        ).select_related("organization", "created_by", "company")

    def perform_create(self, serializer):
        serializer.save(organization=self.organization, created_by=self.request.user)


class InvoiceItemViewSet(OrganizationScopedViewSet):
    serializer_class = InvoiceItemSerializer

    def get_queryset(self):
        return InvoiceItem.objects.filter(
            invoice__organization=self.organization,
            invoice__company__owner=self.request.user,
        ).select_related("invoice", "invoice__company")

    def perform_create(self, serializer):
        invoice = serializer.validated_data["invoice"]
        if invoice.organization_id != self.organization.id:
            raise ValidationError({"invoice": _("Invoice is not in this organization")})
        if invoice.company.owner_id != self.request.user.id:
            raise ValidationError({"invoice": _("Invoice does not belong to the current user")})
        serializer.save()