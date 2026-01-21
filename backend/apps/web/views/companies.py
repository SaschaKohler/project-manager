"""Company management views."""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from apps.invoices.models import Company, Invoice

from .utils import web_shell_context


class BaseCompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "tagline",
            "website",
            "phone",
            "email",
            "logo",
            "account_holder",
            "iban",
            "bic",
            "bank_name",
            "default_pdf_template",
            "theme_color_primary",
            "theme_color_secondary",
            "theme_color_accent",
        ]

    default_pdf_template = forms.ChoiceField(
        required=True,
        choices=Invoice.PdfTemplate.choices,
    )
    theme_color_primary = forms.RegexField(
        required=True,
        regex=r"^#[0-9a-fA-F]{6}$",
        error_messages={"invalid": _("Enter a valid hex color (e.g. #7e56c2).")},
    )
    theme_color_secondary = forms.RegexField(
        required=True,
        regex=r"^#[0-9a-fA-F]{6}$",
        error_messages={"invalid": _("Enter a valid hex color (e.g. #6b9080).")},
    )
    theme_color_accent = forms.RegexField(
        required=True,
        regex=r"^#[0-9a-fA-F]{6}$",
        error_messages={"invalid": _("Enter a valid hex color (e.g. #c9a227).")},
    )

    logo = forms.FileField(required=False)

    def __init__(
        self,
        *args: Any,
        user,
        organization,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._user = user
        self._organization = organization


class CompanyCreateForm(BaseCompanyForm):
    def save(self, commit: bool = True) -> Company:
        instance: Company = super().save(commit=False)
        instance.owner = self._user
        instance.organization = self._organization
        if commit:
            instance.save()
        return instance


class CompanyUpdateForm(BaseCompanyForm):
    def save(self, commit: bool = True) -> Company:
        instance: Company = super().save(commit=False)
        if commit:
            instance.save()
        return instance


@login_required
def companies_page(request: HttpRequest) -> HttpResponse:
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    companies = Company.objects.filter(organization=org, owner=request.user).order_by("name")

    context = {
        **web_shell_context(request),
        "companies": companies,
        "form": CompanyCreateForm(user=request.user, organization=org),
    }
    return render(request, "web/app/companies/page.html", context)


@login_required
def companies_create(request: HttpRequest) -> HttpResponse:
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    form = CompanyCreateForm(request.POST, request.FILES, user=request.user, organization=org)
    if not form.is_valid():
        return HttpResponse(_("Invalid form"), status=400)

    company = form.save()

    if request.headers.get("HX-Request") == "true":
        row_html = render_to_string(
            "web/app/companies/_company_row.html",
            {**web_shell_context(request), "company": company},
            request=request,
        )
        total = Company.objects.filter(organization=org, owner=request.user).count()
        count_html = (
            f'<div id="company-count" class="text-xs text-zinc-500" '
            f'hx-swap-oob="outerHTML">{total} {_("total")}</div>'
        )
        return HttpResponse(row_html + count_html)

    return redirect("web:companies")


@login_required
def companies_edit(request: HttpRequest, company_id) -> HttpResponse:
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    company = Company.objects.filter(id=company_id, organization=org, owner=request.user).first()
    if company is None:
        raise Http404()

    context = {
        **web_shell_context(request),
        "company": company,
        "form": CompanyUpdateForm(instance=company, user=request.user, organization=org),
    }
    return render(request, "web/app/companies/edit.html", context)


@login_required
def companies_update(request: HttpRequest, company_id) -> HttpResponse:
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    company = Company.objects.filter(id=company_id, organization=org, owner=request.user).first()
    if company is None:
        raise Http404()

    form = CompanyUpdateForm(request.POST, request.FILES, instance=company, user=request.user, organization=org)
    if not form.is_valid():
        return HttpResponse(_("Invalid form"), status=400)

    form.save()
    return redirect("web:companies")
