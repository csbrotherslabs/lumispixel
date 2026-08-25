from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import ClientProfile
from apps.accounts.onboarding import get_client_onboarding_resume_url

from .forms import ClientOnboardingProfileForm


CLIENT_DESTINATION_ROUTE = "clients:dashboard"
CLIENT_TOTAL_STEPS = 3


def _client_profile(user):
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    return profile


def _completed_client_destination(profile):
    if profile.onboarding_completed:
        return redirect(CLIENT_DESTINATION_ROUTE)
    return None


def _client_onboarding_profile_or_response(request):
    if not request.user.is_client:
        raise PermissionDenied("Only client accounts can complete client onboarding.")
    profile = _client_profile(request.user)
    completed_response = _completed_client_destination(profile)
    if completed_response:
        return None, completed_response
    return profile, None


def _set_client_step(profile, step):
    if profile.onboarding_step != step:
        profile.onboarding_step = step
        profile.save(update_fields=["onboarding_step", "updated_at"])


@login_required
@require_GET
def setup_dashboard(request):
    if request.user.is_photographer:
        return redirect("photographers:setup-dashboard")
    if not request.user.is_client:
        return redirect("accounts:post-login-redirect")
    profile = _client_profile(request.user)
    if profile.onboarding_completed:
        return redirect(CLIENT_DESTINATION_ROUTE)
    step = profile.onboarding_step if profile.onboarding_step in range(1, CLIENT_TOTAL_STEPS + 1) else 1
    context = {
        "setup_role": "client",
        "profile": profile,
        "current_step": step,
        "total_steps": CLIENT_TOTAL_STEPS,
        "progress_percent": round((step - 1) / CLIENT_TOTAL_STEPS * 100),
        "continue_url": get_client_onboarding_resume_url(profile),
        "review_url": reverse("clients:onboarding-welcome"),
        "feature_cards": ["Find My Photos", "Upload Selfie", "Enter Event Code", "Saved Photos", "Purchases"],
    }
    return render(request, "clients/client_setup_dashboard.html", context)


@login_required
@require_GET
def onboarding_welcome(request):
    profile, response = _client_onboarding_profile_or_response(request)
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
    form = ClientOnboardingProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        _set_client_step(profile, 3)
        return redirect("clients:onboarding-how-it-works")
    context = {"form": form, "profile": profile, "current_step": 2, "title_id": "client-onboarding-profile-title"}
    return render(request, "clients/onboarding_profile.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_how_it_works(request):
    profile, response = _client_onboarding_profile_or_response(request)
    if response:
        return response
    if request.method == "POST":
        profile.onboarding_completed = True
        profile.onboarding_step = CLIENT_TOTAL_STEPS
        profile.save(update_fields=["onboarding_completed", "onboarding_step", "updated_at"])
        return redirect(CLIENT_DESTINATION_ROUTE)
    context = {"current_step": 3, "title_id": "client-onboarding-how-title"}
    return render(request, "clients/onboarding_how_it_works.html", context)


@login_required
@require_GET
def skip_onboarding(request):
    if request.user.is_photographer:
        return redirect("photographers:setup-dashboard")
    if not request.user.is_client:
        return redirect("accounts:post-login-redirect")
    _client_profile(request.user)
    return redirect("clients:setup-dashboard")


@login_required
@require_GET
def dashboard(request):
    user = request.user
    if user.is_photographer:
        return redirect("accounts:photographer-dashboard")
    if not user.is_client:
        return redirect("accounts:post-login-redirect")
    profile = _client_profile(user)
    if not profile.onboarding_completed:
        return redirect("clients:setup-dashboard")
    display_name = profile.display_name or user.first_name or user.display_name
    context = {"client_profile": profile, "display_name": display_name, "find_photos_url": reverse("accounts:find-photos-placeholder"), "saved_photos_url": "#saved-photos"}
    return render(request, "clients/dashboard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def account_settings(request):
    user = request.user
    if user.is_photographer:
        return redirect("photographer_workspace:settings")
    if not user.is_client:
        return redirect("accounts:post-login-redirect")
    profile = _client_profile(user)
    if not profile.onboarding_completed:
        return redirect("clients:setup-dashboard")
    form = ClientOnboardingProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        user=user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('clients:account-settings')}?saved=1")
    context = {"form": form, "profile": profile, "saved": request.GET.get("saved") == "1"}
    return render(request, "clients/account_settings.html", context)
