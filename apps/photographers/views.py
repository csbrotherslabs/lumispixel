from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import PhotographerProfile
from apps.accounts.onboarding import get_photographer_onboarding_resume_url
from apps.accounts.views import _authenticated_destination_url

from .forms import PhotographerBusinessPreferencesForm, PhotographerOnboardingProfileForm, PhotographerSpecialtiesForm, PhotographerThemeForm

THEME_OPTIONS = [
    {"value": PhotographerProfile.WebsiteTheme.ELEGANT, "name": "Elegant", "description": "Best for wedding, family, portrait, and fine-art photography.", "preview_class": "is-elegant"},
    {"value": PhotographerProfile.WebsiteTheme.MODERN, "name": "Modern Studio", "description": "Best for corporate, commercial, branding, product, and headshot work.", "preview_class": "is-modern"},
    {"value": PhotographerProfile.WebsiteTheme.SPORTS, "name": "Sports & Events", "description": "Best for sports, schools, events, and high-volume photography.", "preview_class": "is-sports"},
]
PHOTOGRAPHER_TOTAL_STEPS = 5


def _photographer_profile(user):
    profile, _ = PhotographerProfile.objects.get_or_create(user=user)
    return profile


def _photographer_onboarding_profile_or_response(request):
    if not request.user.is_photographer:
        return None, redirect("clients:setup-dashboard" if request.user.is_client else _authenticated_destination_url(request, request.user))
    profile = _photographer_profile(request.user)
    if profile.onboarding_completed:
        return None, redirect("accounts:photographer-dashboard")
    return profile, None


def _set_photographer_step(profile, step):
    if profile.onboarding_step != step:
        profile.onboarding_step = step
        profile.save(update_fields=["onboarding_step", "updated_at"])


def _context(step, title_id, **extra):
    context = {"current_step": step, "total_steps": PHOTOGRAPHER_TOTAL_STEPS, "title_id": title_id}
    context.update(extra)
    return context


@login_required
@require_GET
def setup_dashboard(request):
    if request.user.is_client:
        return redirect("clients:setup-dashboard")
    if not request.user.is_photographer:
        return redirect("accounts:post-login-redirect")
    profile = _photographer_profile(request.user)
    if profile.onboarding_completed:
        return redirect("accounts:photographer-dashboard")
    step = profile.onboarding_step if profile.onboarding_step in range(1, PHOTOGRAPHER_TOTAL_STEPS + 1) else 1
    context = {
        "setup_role": "photographer",
        "profile": profile,
        "current_step": step,
        "total_steps": PHOTOGRAPHER_TOTAL_STEPS,
        "progress_percent": round((step - 1) / PHOTOGRAPHER_TOTAL_STEPS * 100),
        "continue_url": get_photographer_onboarding_resume_url(profile),
        "review_url": reverse("photographers:onboarding-welcome"),
        "feature_cards": ["Galleries", "Upload Photos", "AI Workspace", "Client Website", "Sales", "Theme Selection"],
    }
    return render(request, "photographers/photographer_setup_dashboard.html", context)


@login_required
@require_GET
def onboarding_welcome(request):
    _, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    return render(request, "photographers/onboarding_welcome.html", _context(1, "photographer-onboarding-welcome-title"))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_profile(request):
    profile, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    form = PhotographerOnboardingProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        _set_photographer_step(profile, 3)
        return redirect("photographers:onboarding-specialties")
    return render(request, "photographers/onboarding_profile.html", _context(2, "photographer-onboarding-profile-title", form=form, profile=profile))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_specialties(request):
    profile, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    form = PhotographerSpecialtiesForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_photographer_step(profile, 4)
        return redirect("photographers:onboarding-business")
    return render(request, "photographers/onboarding_specialties.html", _context(3, "photographer-onboarding-specialties-title", form=form))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_business(request):
    profile, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    form = PhotographerBusinessPreferencesForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_photographer_step(profile, 5)
        return redirect("photographers:onboarding-theme")
    return render(request, "photographers/onboarding_business.html", _context(4, "photographer-onboarding-business-title", form=form))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_theme(request):
    profile, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    form = PhotographerThemeForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.onboarding_completed = True
        profile.onboarding_step = PHOTOGRAPHER_TOTAL_STEPS
        profile.save()
        form.save_m2m()
        return redirect("accounts:photographer-dashboard")
    return render(request, "photographers/onboarding_theme.html", _context(5, "photographer-onboarding-theme-title", form=form, theme_options=THEME_OPTIONS))


@login_required
@require_GET
def skip_onboarding(request):
    if request.user.is_client:
        return redirect("clients:setup-dashboard")
    if not request.user.is_photographer:
        return redirect("accounts:post-login-redirect")
    _photographer_profile(request.user)
    return redirect("photographers:setup-dashboard")
