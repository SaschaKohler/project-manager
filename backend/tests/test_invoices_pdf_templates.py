import pytest
from django.urls import reverse

from apps.invoices.models import Invoice


@pytest.mark.django_db
def test_invoice_get_pdf_template_name_defaults_to_classic(
    user_factory,
    organization_factory,
    company_factory,
):
    user = user_factory()
    org = organization_factory(user=user)
    company = company_factory(organization=org, owner=user)

    invoice = Invoice(
        organization=org,
        company=company,
        recipient_name="Test",
        recipient_address="Street 1",
        recipient_zip="1234",
        recipient_city="City",
        created_by=user,
    )

    assert invoice.get_pdf_template_name() == "web/invoices/pdf.html"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "template_key,expected",
    [
        (Invoice.PdfTemplate.MODERN, "web/invoices/pdf_modern.html"),
        (Invoice.PdfTemplate.ELEGANT, "web/invoices/pdf_elegant.html"),
        (Invoice.PdfTemplate.MINIMAL, "web/invoices/pdf_minimal.html"),
        (Invoice.PdfTemplate.CLASSIC, "web/invoices/pdf.html"),
    ],
)
def test_invoice_get_pdf_template_name_maps_choices(
    user_factory,
    organization_factory,
    company_factory,
    template_key,
    expected,
):
    user = user_factory()
    org = organization_factory(user=user)
    company = company_factory(organization=org, owner=user)

    invoice = Invoice(
        organization=org,
        company=company,
        recipient_name="Test",
        recipient_address="Street 1",
        recipient_zip="1234",
        recipient_city="City",
        created_by=user,
        pdf_template=template_key,
    )

    assert invoice.get_pdf_template_name() == expected


@pytest.mark.django_db
def test_invoices_pdf_uses_invoice_template(
    mocker,
    client,
    user_factory,
    organization_factory,
    company_factory,
):
    user = user_factory()
    org = organization_factory(user=user)
    company = company_factory(organization=org, owner=user)

    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    invoice = Invoice.objects.create(
        organization=org,
        company=company,
        recipient_name="Test",
        recipient_address="Street 1",
        recipient_zip="1234",
        recipient_city="City",
        created_by=user,
        pdf_template=Invoice.PdfTemplate.MODERN,
    )

    render_to_string = mocker.patch("django.template.loader.render_to_string", return_value="<html></html>")

    class _HTML:
        def __init__(self, string, base_url):
            self.string = string
            self.base_url = base_url

        def write_pdf(self):
            return b"%PDF-TEST"

    mocker.patch("weasyprint.HTML", _HTML)

    url = reverse("web:invoices_pdf", kwargs={"invoice_id": invoice.id})
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    render_to_string.assert_called_once()
    called_template = render_to_string.call_args[0][0]
    assert called_template == "web/invoices/pdf_modern.html"


@pytest.mark.django_db
def test_invoices_pdf_allows_template_override(
    mocker,
    client,
    user_factory,
    organization_factory,
    company_factory,
):
    user = user_factory()
    org = organization_factory(user=user)
    company = company_factory(organization=org, owner=user)

    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    invoice = Invoice.objects.create(
        organization=org,
        company=company,
        recipient_name="Test",
        recipient_address="Street 1",
        recipient_zip="1234",
        recipient_city="City",
        created_by=user,
        pdf_template=Invoice.PdfTemplate.MODERN,
    )

    render_to_string = mocker.patch("django.template.loader.render_to_string", return_value="<html></html>")

    class _HTML:
        def __init__(self, string, base_url):
            self.string = string
            self.base_url = base_url

        def write_pdf(self):
            return b"%PDF-TEST"

    mocker.patch("weasyprint.HTML", _HTML)

    url = reverse("web:invoices_pdf", kwargs={"invoice_id": invoice.id})
    resp = client.get(url, {"template": "elegant"})

    assert resp.status_code == 200
    called_template = render_to_string.call_args[0][0]
    assert called_template == "web/invoices/pdf_elegant.html"


@pytest.mark.django_db
def test_invoices_pdf_preview_returns_html(
    mocker,
    client,
    user_factory,
    organization_factory,
    company_factory,
):
    user = user_factory()
    org = organization_factory(user=user)
    company = company_factory(organization=org, owner=user)

    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    invoice = Invoice.objects.create(
        organization=org,
        company=company,
        recipient_name="Test",
        recipient_address="Street 1",
        recipient_zip="1234",
        recipient_city="City",
        created_by=user,
        pdf_template=Invoice.PdfTemplate.CLASSIC,
    )

    mocker.patch("django.template.loader.render_to_string", return_value="<html>preview</html>")

    url = reverse("web:invoices_pdf", kwargs={"invoice_id": invoice.id})
    resp = client.get(url, {"preview": "1", "template": "minimal"})

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/html")
    assert resp["X-Frame-Options"] == "SAMEORIGIN"
    assert b"preview" in resp.content


@pytest.mark.django_db
def test_invoices_pdf_save_persists_template_choice(
    mocker,
    client,
    user_factory,
    organization_factory,
    company_factory,
):
    user = user_factory()
    org = organization_factory(user=user)
    company = company_factory(organization=org, owner=user)

    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    invoice = Invoice.objects.create(
        organization=org,
        company=company,
        recipient_name="Test",
        recipient_address="Street 1",
        recipient_zip="1234",
        recipient_city="City",
        created_by=user,
        pdf_template=Invoice.PdfTemplate.MODERN,
    )

    mocker.patch("django.template.loader.render_to_string", return_value="<html>preview</html>")

    url = reverse("web:invoices_pdf", kwargs={"invoice_id": invoice.id})
    resp = client.get(url, {"preview": "1", "template": "elegant", "save": "1"})

    assert resp.status_code == 200
    invoice.refresh_from_db()
    assert invoice.pdf_template == Invoice.PdfTemplate.ELEGANT
