from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenants.models import Membership, Organization, OrganizationInvitation

from .utils import web_shell_context


@login_required
def team_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    org = request.active_org
    members = (
        Membership.objects.filter(organization=org)
        .select_related("user")
        .order_by("user__email")
    )
    member_user_ids = list(members.values_list("user_id", flat=True))

    User = get_user_model()
    available_users = (
        User.objects.exclude(id__in=member_user_ids)
        .filter(is_active=True)
        .filter(Q(email__isnull=False) & ~Q(email=""))
        .order_by("email")
    )
    invitations = OrganizationInvitation.objects.filter(
        organization=org, status=OrganizationInvitation.Status.PENDING
    ).order_by("-created_at")

    last_invite_url = request.session.pop("last_invite_url", None)
    context = {
        **web_shell_context(request),
        "members": members,
        "available_users": available_users,
        "invitations": invitations,
        "last_invite_url": last_invite_url,
    }
    return render(request, "web/app/team/page.html", context)


@login_required
def team_invite(request):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    if not Membership.objects.filter(organization=org, user=request.user).exists():
        raise Http404()

    email = (request.POST.get("email") or "").strip().lower()
    role = (request.POST.get("role") or "").strip().upper() or Membership.Role.MEMBER

    if not email:
        return HttpResponse("", status=400)
    if role not in {
        Membership.Role.ADMIN,
        Membership.Role.MEMBER,
        Membership.Role.OWNER,
    }:
        return HttpResponse("", status=400)

    User = get_user_model()
    existing_user = User.objects.filter(email__iexact=email).first()

    if Membership.objects.filter(organization=org, user__email__iexact=email).exists():
        return redirect("web:team")

    expires_at = timezone.now() + timedelta(days=14)
    invitation = OrganizationInvitation.objects.create(
        organization=org,
        email=email,
        role=role,
        invited_by=request.user,
        expires_at=expires_at,
    )

    invite_url = f"{request.scheme}://{request.get_host()}/app/invite/{invitation.token}/"

    if existing_user is None:
        request.session["last_invite_url"] = invite_url
        send_mail(
            subject=f"Invitation to join {org.name}",
            message=(
                f"You have been invited to join {org.name}.\n\n"
                f"Accept the invitation here:\n{invite_url}\n\n"
                f"This invitation expires on {invitation.expires_at:%Y-%m-%d}."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@localhost",
            recipient_list=[email],
            fail_silently=False,
        )

    return redirect("web:team")


@login_required
def invite_accept(request, token):
    try:
        invitation = OrganizationInvitation.objects.select_related("organization").get(
            token=token
        )
    except OrganizationInvitation.DoesNotExist as exc:
        raise Http404() from exc

    if invitation.status != OrganizationInvitation.Status.PENDING:
        raise Http404()
    if invitation.is_expired():
        OrganizationInvitation.objects.filter(id=invitation.id).update(
            status=OrganizationInvitation.Status.EXPIRED
        )
        raise Http404()

    if request.method == "GET":
        context = {
            "org": invitation.organization,
            "orgs": Organization.objects.filter(memberships__user=request.user).distinct(),
            "invitation": invitation,
        }
        return render(request, "web/app/team/invite_accept.html", context)

    if request.method != "POST":
        raise Http404()

    if request.user.email.lower() != invitation.email.lower():
        return HttpResponse("", status=403)

    with transaction.atomic():
        Membership.objects.get_or_create(
            organization=invitation.organization,
            user=request.user,
            defaults={"role": invitation.role},
        )
        OrganizationInvitation.objects.filter(id=invitation.id).update(
            status=OrganizationInvitation.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )

    request.session["active_org_id"] = str(invitation.organization_id)
    return redirect("web:home")
