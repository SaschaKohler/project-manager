from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ['total']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'recipient_name', 'invoice_date', 'total', 'organization']
    list_filter = ['organization', 'invoice_date']
    search_fields = ['invoice_number', 'recipient_name']
    readonly_fields = ['invoice_number', 'subtotal', 'vat_amount', 'total']
    inlines = [InvoiceItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's organizations
        from apps.tenants.models import Membership
        user_orgs = Membership.objects.filter(user=request.user).values_list('organization', flat=True)
        return qs.filter(organization__in=user_orgs)


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'position', 'description', 'quantity', 'unit_price', 'total']
    list_filter = ['invoice__organization']
    search_fields = ['description', 'invoice__invoice_number']
    readonly_fields = ['total']