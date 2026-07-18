from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import PhotographerProfile

from .forms import (
    PhotographerBusinessPreferencesForm,
    PhotographerOnboardingProfileForm,
    PhotographerSpecialtiesForm,
    PhotographerThemeForm,
)

THEME_OPTIONS = [
    {"value": PhotographerProfile.WebsiteTheme.ELEGANT, "name": "Elegant", "description": "Best for wedding, family, portrait, and fine-art photography.", "preview_class": "is-elegant"},
    {"value": PhotographerProfile.WebsiteTheme.MODERN, "name": "Modern Studio", "description": "Best for corporate, commercial, branding, product, and headshot work.", "preview_class": "is-modern"},
    {"value": PhotographerProfile.WebsiteTheme.SPORTS, "name": "Sports & Events", "description": "Best for sports, schools, events, and high-volume photography.", "preview_class": "is-sports"},
]


def _photographer_profile(user):
    profile, _ = PhotographerProfile.objects.get_or_create(user=user)
    return profile


def _photographer_onboarding_profile(request):
    if not request.user.is_photographer:
        raise PermissionDenied("Only photographer accounts can complete photographer onboarding.")
    return _photographer_profile(request.user)


def _context(step, title_id, **extra):
    context = {"current_step": step, "total_steps": 5, "title_id": title_id}
    context.update(extra)
    return context


@login_required
@require_GET
def onboarding_welcome(request):
    _photographer_onboarding_profile(request)
    return render(request, "photographers/onboarding_welcome.html", _context(1, "photographer-onboarding-welcome-title"))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_profile(request):
    profile = _photographer_onboarding_profile(request)
    form = PhotographerOnboardingProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("photographers:onboarding-specialties")
    return render(request, "photographers/onboarding_profile.html", _context(2, "photographer-onboarding-profile-title", form=form, profile=profile))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_specialties(request):
    profile = _photographer_onboarding_profile(request)
    form = PhotographerSpecialtiesForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("photographers:onboarding-business")
    return render(request, "photographers/onboarding_specialties.html", _context(3, "photographer-onboarding-specialties-title", form=form))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_business(request):
    profile = _photographer_onboarding_profile(request)
    form = PhotographerBusinessPreferencesForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("photographers:onboarding-theme")
    return render(request, "photographers/onboarding_business.html", _context(4, "photographer-onboarding-business-title", form=form))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_theme(request):
    profile = _photographer_onboarding_profile(request)
    form = PhotographerThemeForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:photographer-onboarding")
    return render(request, "photographers/onboarding_theme.html", _context(5, "photographer-onboarding-theme-title", form=form, theme_options=THEME_OPTIONS))
