"""
Authentication and registration views.
"""
from django.contrib.auth import login
from django.shortcuts import redirect, render

from apps.accounts.forms import CustomUserCreationForm


def register(request):
    """User registration page."""
    if request.user.is_authenticated:
        return redirect("web:onboarding")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("web:onboarding")
    else:
        form = CustomUserCreationForm()

    return render(request, "web/auth/register.html", {"form": form})


def healthz(request):
    """Health check endpoint."""
    from django.http import HttpResponse
    return HttpResponse("ok")
