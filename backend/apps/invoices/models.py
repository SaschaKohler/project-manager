import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.conf import settings

from apps.tenants.models import Organization


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="companies"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="companies",
    )

    name = models.CharField(max_length=255)
    tagline = models.CharField(max_length=255, blank=True, default="")
    website = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=64, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    account_holder = models.CharField(max_length=255, blank=True, default="")
    iban = models.CharField(max_length=64, blank=True, default="")
    bic = models.CharField(max_length=32, blank=True, default="")
    bank_name = models.CharField(max_length=255, blank=True, default="")

    default_pdf_template = models.CharField(
        max_length=32,
        choices=[
            ("classic", _("Classic")),
            ("modern", _("Modern")),
            ("elegant", _("Elegant")),
            ("minimal", _("Minimal")),
        ],
        default="classic",
    )
    theme_color_primary = models.CharField(max_length=7, default="#7e56c2")
    theme_color_secondary = models.CharField(max_length=7, default="#6b9080")
    theme_color_accent = models.CharField(max_length=7, default="#c9a227")

    logo = models.FileField(upload_to="company_logos/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "owner", "name")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoices"
    )
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="invoices"
    )
    invoice_number = models.CharField(max_length=20, editable=False)
    invoice_date = models.DateField(default=timezone.now)
    service_date = models.DateField(default=timezone.now)

    # Recipient information
    recipient_name = models.CharField(max_length=255)
    recipient_address = models.TextField()
    recipient_zip = models.CharField(max_length=10, default='')
    recipient_city = models.CharField(max_length=255, default='')

    # Financial information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # 0% for Kleinunternehmer
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class PdfTemplate(models.TextChoices):
        CLASSIC = "classic", _("Classic")
        MODERN = "modern", _("Modern")
        ELEGANT = "elegant", _("Elegant")
        MINIMAL = "minimal", _("Minimal")

    pdf_template = models.CharField(
        max_length=32,
        choices=PdfTemplate.choices,
        default=PdfTemplate.CLASSIC,
    )

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "company", "invoice_number"],
                name="uniq_invoice_number_per_company",
            )
        ]

    def __str__(self) -> str:
        return f"Invoice {self.invoice_number}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    def _generate_invoice_number(self):
        """Generate invoice number in format NNN-DD-MM-YYYY"""
        today = timezone.now().date()
        day = today.day
        month = today.month
        year = today.year

        # Find the highest number for today
        existing = Invoice.objects.filter(
            organization=self.organization,
            company=self.company,
            invoice_number__endswith=f"-{day:02d}-{month:02d}-{year}"
        ).order_by('-invoice_number')

        if existing.exists():
            last_invoice = existing.first()
            if last_invoice:
                last_number = last_invoice.invoice_number
                # Extract the NNN part
                try:
                    number_part = int(last_number.split('-')[0])
                    next_number = number_part + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
        else:
            next_number = 1

        return f"{next_number:03d}-{day:02d}-{month:02d}-{year}"

    def update_totals(self):
        """Update subtotal, VAT, and total based on invoice items"""
        from django.db.models import Sum
        items_agg = self.items.aggregate(
            subtotal=Sum('total')
        )
        self.subtotal = items_agg['subtotal'] or Decimal('0.00')
        self.vat_amount = (self.subtotal * self.vat_rate / 100).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.vat_amount
        super().save(update_fields=['subtotal', 'vat_amount', 'total'])

    def get_pdf_template_name(self) -> str:
        template = self.pdf_template
        if template == self.PdfTemplate.MODERN:
            return "web/invoices/pdf_modern.html"
        if template == self.PdfTemplate.ELEGANT:
            return "web/invoices/pdf_elegant.html"
        if template == self.PdfTemplate.MINIMAL:
            return "web/invoices/pdf_minimal.html"
        return "web/invoices/pdf.html"


class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items"
    )
    position = models.PositiveIntegerField(default=1)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    class Meta:
        ordering = ["position"]

    def __str__(self) -> str:
        return f"Item {self.position}: {self.description[:50]}"

    def save(self, *args, **kwargs):
        self.total = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)