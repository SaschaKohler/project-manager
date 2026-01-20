from rest_framework import serializers

from .models import Invoice, InvoiceItem


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

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'service_date',
            'recipient_name', 'recipient_address', 'recipient_zip_city',
            'subtotal', 'vat_rate', 'vat_amount', 'total',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'subtotal', 'vat_amount', 'total',
            'created_at', 'updated_at'
        ]