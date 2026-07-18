from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import ClientProfile, User

from .forms import ClientOnboardingProfileForm


CLIENT_DESTINATION_ROUTE = "accounts:client-dashboard"


def _client_profile(user):
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    return profile


def _completed_client_destination(profile):
    if profile.onboarding_completed:
        return redirect(CLIENT_DESTINATION_ROUTE)
    return None


def _client_onboarding_profile_or_response(request):
    if request.user.primary_role != User.PrimaryRole.CLIENT:
        raise PermissionDenied("Only client accounts can complete client onboarding.")
    profile = _client_profile(request.user)
    completed_response = _completed_client_destination(profile)
    if completed_response:
        return None, completed_response
    return profile, None


@login_required
@require_GET
def onboarding_welcome(request):
    _, response = _client_onboarding_profile_or_response(request)
    if response:
        return response
    context = {"current_step": 1, "title_id": "client-onboarding-welcome-title"}
    return render(request, "clients/onboarding_welcome.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_profile(request):
    profile, response = _client_onboarding_profile_or_response(request)
    if response:
        return response
    form = ClientOnboardingProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("clients:onboarding-how-it-works")
    context = {
        "form": form,
        "profile": profile,
        "current_step": 2,
        "title_id": "client-onboarding-profile-title",
    }
    return render(request, "clients/onboarding_profile.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_how_it_works(request):
    profile, response = _client_onboarding_profile_or_response(request)
    if response:
        return response
    if request.method == "POST":
        profile.onboarding_completed = True
        profile.save(update_fields=["onboarding_completed", "updated_at"])
        return redirect(CLIENT_DESTINATION_ROUTE)
    context = {"current_step": 3, "title_id": "client-onboarding-how-title"}
    return render(request, "clients/onboarding_how_it_works.html", context)
