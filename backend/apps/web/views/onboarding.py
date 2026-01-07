from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.tenants.models import Membership, Organization

from .utils import web_shell_context


@login_required
def onboarding(request):
    if request.active_org is not None:
        return redirect("web:home")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, _("Please provide a workspace name"))
            return render(request, "web/app/onboarding.html")

        base_slug = slugify(name) or "workspace"
        slug = base_slug
        idx = 1
        while Organization.objects.filter(slug=slug).exists():
            idx += 1
            slug = f"{base_slug}-{idx}"

        org = Organization.objects.create(name=name, slug=slug)
        Membership.objects.create(
            organization=org, user=request.user, role=Membership.Role.OWNER
        )
        request.session["active_org_id"] = str(org.id)

        return redirect("web:home")

    return render(request, "web/app/onboarding.html")


@login_required
def workspaces_new(request):
    if request.method == "GET":
        return render(
            request,
            "web/app/workspaces/new.html",
            {**web_shell_context(request)},
        )

    if request.method != "POST":
        raise Http404()

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, _("Please provide a workspace name"))
        return render(
            request,
            "web/app/workspaces/new.html",
            {**web_shell_context(request)},
        )

    base_slug = slugify(name) or "workspace"
    slug = base_slug
    idx = 1
    while Organization.objects.filter(slug=slug).exists():
        idx += 1
        slug = f"{base_slug}-{idx}"

    org = Organization.objects.create(name=name, slug=slug)
    Membership.objects.create(
        organization=org, user=request.user, role=Membership.Role.OWNER
    )
    request.session["active_org_id"] = str(org.id)
    return redirect("web:home")


@login_required
def switch_org(request, org_id):
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist as exc:
        raise Http404() from exc

    if not Membership.objects.filter(user=request.user, organization=org).exists():
        raise Http404()

    request.session["active_org_id"] = str(org.id)
    return redirect("web:home")
