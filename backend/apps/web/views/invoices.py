"""
Invoice management views.
"""
from decimal import Decimal

from django import forms

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.invoices.models import Company, Invoice, InvoiceItem

from .utils import web_shell_context


class InvoiceCreateForm(forms.Form):
    company = forms.ModelChoiceField(queryset=Company.objects.none(), required=True)
    recipient_name = forms.CharField(required=True, max_length=255)
    recipient_address = forms.CharField(required=False)
    recipient_zip = forms.CharField(required=False, max_length=10)
    recipient_city = forms.CharField(required=True, max_length=255)
    invoice_date = forms.DateField(required=False)
    service_date = forms.DateField(required=False)
    pdf_template = forms.ChoiceField(required=False, choices=Invoice.PdfTemplate.choices)

    def __init__(self, *args, user, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        self._organization = organization
        self.fields["company"].queryset = Company.objects.filter(
            organization=organization,
            owner=user,
        )

    def clean_company(self):
        company = self.cleaned_data["company"]
        if company.owner_id != self._user.id:
            raise forms.ValidationError(_("Company does not belong to the current user"))
        if company.organization_id != self._organization.id:
            raise forms.ValidationError(_("Company does not belong to the current organization"))
        return company


@login_required
def invoices_page(request):
    """List all invoices."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    companies = Company.objects.filter(organization=org, owner=request.user).order_by("name")
    selected_company = None
    selected_company_id = (request.GET.get("company") or "").strip()
    if selected_company_id:
        selected_company = companies.filter(id=selected_company_id).first()

    invoices_qs = Invoice.objects.filter(
        organization=org,
        company__in=companies,
    )
    if selected_company is not None:
        invoices_qs = invoices_qs.filter(company=selected_company)

    invoices = invoices_qs.select_related("company").order_by("-created_at")

    from django.utils import timezone
    today = timezone.now().date()

    context = {
        **web_shell_context(request),
        "companies": companies,
        "selected_company": selected_company,
        "invoices": invoices,
        "today": today,
    }
    return render(request, "web/app/invoices/page.html", context)


@login_required
def invoices_create(request):
    """Create a new invoice."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org

    # Check if this is a preview request
    is_preview = request.POST.get('preview') == '1' or request.GET.get('preview') == '1'

    form = InvoiceCreateForm(request.POST, user=request.user, organization=org)
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))
        message = first_error[0] if first_error else _("Invalid form")
        return JsonResponse({"error": message}, status=400)

    company = form.cleaned_data["company"]
    recipient_name = form.cleaned_data["recipient_name"]
    recipient_address = form.cleaned_data.get("recipient_address") or ""
    recipient_zip = form.cleaned_data.get("recipient_zip") or ""
    recipient_city = form.cleaned_data["recipient_city"]
    invoice_date = form.cleaned_data.get("invoice_date") or timezone.now().date()
    service_date = form.cleaned_data.get("service_date") or timezone.now().date()
    pdf_template = (form.cleaned_data.get("pdf_template") or "").strip()
    if not pdf_template:
        pdf_template = company.default_pdf_template

    # Create invoice (temporary for preview, permanent for creation)
    invoice = Invoice(
        organization=org,
        company=company,
        recipient_name=recipient_name,
        recipient_address=recipient_address,
        recipient_zip=recipient_zip,
        recipient_city=recipient_city,
        invoice_date=invoice_date,
        service_date=service_date,
        created_by=request.user,
    )

    if pdf_template in {choice for choice, _label in Invoice.PdfTemplate.choices}:
        invoice.pdf_template = pdf_template

    # Generate invoice number for preview
    if is_preview:
        invoice.invoice_number = invoice._generate_invoice_number()
    else:
        invoice.save()  # Only save if not preview

    # Create invoice items - parse indexed field names
    item_descriptions = []
    item_quantities = []
    item_unit_prices = []

    # Parse all POST data for indexed fields
    for key, value in request.POST.items():
        if key.startswith("item_description_"):
            try:
                index = int(key.split("_")[-1])
                while len(item_descriptions) <= index:
                    item_descriptions.append("")
                item_descriptions[index] = value
            except (ValueError, IndexError):
                continue
        elif key.startswith("item_quantity_"):
            try:
                index = int(key.split("_")[-1])
                while len(item_quantities) <= index:
                    item_quantities.append("")
                item_quantities[index] = value
            except (ValueError, IndexError):
                continue
        elif key.startswith("item_unit_price_"):
            try:
                index = int(key.split("_")[-1])
                while len(item_unit_prices) <= index:
                    item_unit_prices.append("")
                item_unit_prices[index] = value
            except (ValueError, IndexError):
                continue

    # Debug logging (commented out for production)
    # print(f"DEBUG: All POST data: {dict(request.POST)}")
    # print(f"DEBUG: item_descriptions = {item_descriptions}")
    # print(f"DEBUG: item_quantities = {item_quantities}")
    # print(f"DEBUG: item_unit_prices = {item_unit_prices}")

    # Ensure all lists have the same length
    max_len = max(len(item_descriptions), len(item_quantities), len(item_unit_prices))
    item_descriptions.extend([''] * (max_len - len(item_descriptions)))
    item_quantities.extend([''] * (max_len - len(item_quantities)))
    item_unit_prices.extend([''] * (max_len - len(item_unit_prices)))

    # Create temporary invoice items for calculation
    temp_items = []
    subtotal = Decimal('0.00')

    for i, (desc, qty, price) in enumerate(zip(item_descriptions, item_quantities, item_unit_prices)):
        desc = desc.strip() if desc else ""
        if desc:
            try:
                qty_str = qty.strip() if qty else ""
                price_str = price.strip() if price else ""
                quantity = Decimal(qty_str) if qty_str else Decimal('1.0')
                unit_price = Decimal(price_str) if price_str else Decimal('0.0')
                total = quantity * unit_price
                subtotal += total.quantize(Decimal('0.01'))

                temp_item = {
                    'position': i + 1,
                    'description': desc,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total': float(total.quantize(Decimal('0.01')))
                }
                temp_items.append(temp_item)

                # print(f"DEBUG: Item {i+1}: desc='{desc}', qty={quantity}, price={unit_price}, total={total}")

                if not is_preview:
                    # print(f"DEBUG: Creating InvoiceItem for invoice {invoice.id}: position={i + 1}, desc='{desc}', qty={quantity}, price={unit_price}")
                    try:
                        item = InvoiceItem.objects.create(
                            invoice=invoice,
                            position=i + 1,
                            description=desc,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                        # print(f"DEBUG: Created InvoiceItem with id {item.id}")
                    except Exception as create_error:
                        # print(f"DEBUG: Failed to create InvoiceItem: {create_error}")
                        continue
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error processing item {i+1}: {e}")
                continue

    # Calculate totals
    if not is_preview:
        # For real invoices, recalculate totals from database
        invoice.update_totals()
    else:
        # For preview, use calculated values
        vat_amount = (subtotal * invoice.vat_rate / 100).quantize(Decimal('0.01'))
        total = subtotal + vat_amount
        invoice.subtotal = subtotal
        invoice.vat_amount = vat_amount
        invoice.total = total

    if is_preview:
        # Return preview HTML
        context = {
            'invoice': invoice,
            'items': temp_items,
            'is_preview': True
        }
        html = render_to_string('web/app/invoices/preview.html', context, request)
        response = HttpResponse(html, content_type="text/html")
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response

    if request.headers.get("HX-Request") == "true":
        row_html = render_to_string(
            "web/app/invoices/_invoice_row.html",
            {**web_shell_context(request), "invoice": invoice},
            request=request,
        )
        return HttpResponse(row_html)

    return redirect("web:invoices")


@login_required
def invoices_detail(request, invoice_id):
    """View invoice details."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    try:
        invoice = Invoice.objects.select_related("company").get(
            id=invoice_id,
            organization=org,
            company__owner=request.user,
        )
    except Invoice.DoesNotExist as exc:
        raise Http404() from exc

    context = {**web_shell_context(request), "invoice": invoice}
    return render(request, "web/app/invoices/detail.html", context)


@login_required
def invoices_pdf(request, invoice_id):
    """Generate PDF for invoice."""
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    try:
        invoice = Invoice.objects.select_related("company").get(
            id=invoice_id,
            organization=org,
            company__owner=request.user,
        )
    except Invoice.DoesNotExist as exc:
        raise Http404() from exc

    try:
        from django.template.loader import render_to_string

        template_override = (request.GET.get("template") or "").strip()
        if template_override in {choice for choice, _label in Invoice.PdfTemplate.choices}:
            invoice.pdf_template = template_override
            if (request.GET.get("save") or "").strip() == "1":
                invoice.save(update_fields=["pdf_template"])

        html_content = render_to_string(
            invoice.get_pdf_template_name(),
            {
                "invoice": invoice,
            },
            request,
        )

        if (request.GET.get("preview") or "").strip() == "1":
            response = HttpResponse(html_content, content_type="text/html")
            response["X-Frame-Options"] = "SAMEORIGIN"
            return response

        # Use weasyprint to generate PDF from HTML template
        from weasyprint import HTML

        # Generate PDF
        html_doc = HTML(string=html_content, base_url=request.build_absolute_uri())
        pdf_file = html_doc.write_pdf()

        # Return PDF response
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice-{invoice.invoice_number}.pdf"'
        return response

    except Exception as e:
        # Return error response
        return HttpResponse(f"PDF generation failed: {str(e)}", status=500, content_type='text/plain')

