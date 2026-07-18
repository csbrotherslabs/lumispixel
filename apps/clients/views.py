from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import ClientProfile

from .forms import ClientOnboardingProfileForm


def _client_profile(user):
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    return profile


@login_required
@require_GET
def onboarding_welcome(request):
    context = {"current_step": 1, "title_id": "client-onboarding-welcome-title"}
    return render(request, "clients/onboarding_welcome.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_profile(request):
    profile = _client_profile(request.user)
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
@require_GET
def onboarding_how_it_works(request):
    context = {"current_step": 3, "title_id": "client-onboarding-how-title"}
    return render(request, "clients/onboarding_how_it_works.html", context)
