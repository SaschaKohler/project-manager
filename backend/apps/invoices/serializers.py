from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from .models import Company, Invoice, InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'position', 'description', 'quantity',
            'unit_price', 'total'
        ]
        read_only_fields = ['id', 'total']


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'service_date',
            'company',
            'recipient_name', 'recipient_address', 'recipient_zip', 'recipient_city',
            'subtotal', 'vat_rate', 'vat_amount', 'total',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'subtotal', 'vat_amount', 'total',
            'created_at', 'updated_at'
        ]

    def validate_company(self, company: Company) -> Company:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        if company.owner_id != user.id:
            raise serializers.ValidationError(_("Company does not belong to the current user"))

        org = self.context.get("organization")
        if org is not None and company.organization_id != org.id:
            raise serializers.ValidationError(_("Company does not belong to the current organization"))

        return company