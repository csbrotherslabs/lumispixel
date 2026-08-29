from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import PhotographerProfile, PhotographerWebsiteProfile, PhotographerWebsiteProject
from apps.accounts.onboarding import get_photographer_onboarding_resume_url
from apps.accounts.views import _authenticated_destination_url

from .forms import PhotographerBusinessPreferencesForm, PhotographerOnboardingProfileForm, PhotographerSpecialtiesForm, PhotographerWebsiteThemeForm, THEME_FIELD_CONFIG, IMAGE_TYPES, MAX_IMAGE_SIZE

THEME_OPTIONS = [
    {"value": PhotographerProfile.WebsiteTheme.BASIC, "slug": "basic", "name": "Basic", "best_for": "Simple landing page", "description": "Uses your existing profile details only.", "required_summary": "No additional information required.", "preview_class": "is-basic", "url_name": "photographers:photographer_onboarding_theme_preview_basic"},
    {"value": PhotographerProfile.WebsiteTheme.ELEGANT, "slug": "elegant", "name": "Elegant", "best_for": "Weddings, portraits, families, fine art", "description": "Romantic full-width imagery with story, galleries, testimonial, and booking CTA.", "required_summary": "Hero, about, featured gallery, booking CTA.", "preview_class": "is-elegant", "url_name": "photographers:photographer_onboarding_theme_preview_elegant"},
    {"value": PhotographerProfile.WebsiteTheme.MODERN_STUDIO, "slug": "modern-studio", "name": "Modern Studio", "best_for": "Corporate, branding, commercial, product, headshots", "description": "Clean split-screen presentation with service cards and consultation CTA.", "required_summary": "Hero, studio intro, services intro, consultation CTA.", "preview_class": "is-modern", "url_name": "photographers:photographer_onboarding_theme_preview_modern_studio"},
    {"value": PhotographerProfile.WebsiteTheme.CINEMATIC, "slug": "cinematic", "name": "Cinematic", "best_for": "Wedding films, events, fashion, lifestyle", "description": "Dark immersive video-forward homepage with story and reel sections.", "required_summary": "Media type, hero, story, contact CTA.", "preview_class": "is-cinematic", "url_name": "photographers:photographer_onboarding_theme_preview_cinematic"},
    {"value": PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL, "slug": "portfolio-editorial", "name": "Portfolio Editorial", "best_for": "Fashion, editorial, fine art, street, creative portraits", "description": "Magazine typography and asymmetrical project showcase.", "required_summary": "Editorial heading, artist statement, project heading, contact statement.", "preview_class": "is-editorial", "url_name": "photographers:photographer_onboarding_theme_preview_portfolio_editorial"},
    {"value": PhotographerProfile.WebsiteTheme.SPORTS_EVENTS, "slug": "sports-events", "name": "Sports & Events", "best_for": "Sports, schools, high-volume and public events", "description": "Action-led design with Find My Photos and event code CTAs.", "required_summary": "Hero, find photos, recent events, booking CTA.", "preview_class": "is-sports", "url_name": "photographers:photographer_onboarding_theme_preview_sports_events"},
]
PHOTOGRAPHER_TOTAL_STEPS = 5


def _photographer_profile(user):
    profile, _ = PhotographerProfile.objects.get_or_create(user=user)
    return profile


def _photographer_onboarding_profile_or_response(request):
    if not request.user.has_photographer_profile:
        destination = "clients:setup-dashboard" if request.user.has_client_profile else _authenticated_destination_url(request, request.user)
        return None, redirect(destination)
    profile = _photographer_profile(request.user)
    if profile.onboarding_completed:
        return None, redirect("photographer_workspace:dashboard")
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
    if not request.user.has_photographer_profile:
        return redirect("clients:setup-dashboard" if request.user.has_client_profile else "accounts:post-login-redirect")
    profile = _photographer_profile(request.user)
    if profile.onboarding_completed:
        return redirect("photographer_workspace:dashboard")
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
    location_parts = [profile.city, profile.state, profile.country]
    location_summary = ", ".join(part for part in location_parts if part)
    location_complete = all(location_parts)
    return render(request, "photographers/onboarding_business.html", _context(4, "photographer-onboarding-business-title", form=form, profile=profile, location_summary=location_summary, location_complete=location_complete))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_theme(request):
    profile, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    action = request.POST.get("action", "finish_setup") if request.method == "POST" else None
    form = PhotographerWebsiteThemeForm(request.POST or None, request.FILES or None, instance=profile, website_profile=website, draft=(action == "save_draft"))
    if request.method == "POST" and form.is_valid():
        profile, website = form.save_theme()
        _save_project_drafts(request, website)
        if action == "save_draft":
            messages.success(request, "Your website theme draft has been saved. You can complete it anytime.")
            return redirect("photographers:setup-dashboard")
        profile.onboarding_completed = True
        profile.onboarding_step = PHOTOGRAPHER_TOTAL_STEPS
        profile.save(update_fields=["onboarding_completed", "onboarding_step", "updated_at"])
        return redirect("photographer_workspace:dashboard")
    return render(request, "photographers/onboarding_theme.html", _context(5, "photographer-onboarding-theme-title", form=form, profile=profile, website=website, projects=list(website.projects.all()[:3]), theme_options=THEME_OPTIONS, theme_panels=_theme_panels(form), theme_field_config=THEME_FIELD_CONFIG))


def _theme_panels(form):
    panels = []
    for option in THEME_OPTIONS:
        key = option["value"]
        if key == PhotographerProfile.WebsiteTheme.BASIC:
            continue
        names = ["hero_image"] + THEME_FIELD_CONFIG[key]["required"] + THEME_FIELD_CONFIG[key]["optional"]
        panels.append({"key": key, "name": option["name"], "fields": [form[name] for name in names if name in form.fields]})
    return panels


def _save_project_drafts(request, website):
    if website.selected_theme != PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL:
        return
    website.projects.all().delete()
    for index in range(3):
        title = request.POST.get(f"project_{index}_title", "").strip()
        description = request.POST.get(f"project_{index}_description", "").strip()
        image = request.FILES.get(f"project_{index}_cover_image")
        if not (title or description or image):
            continue
        project = PhotographerWebsiteProject(photographer_website=website, title=title, description=description, display_order=index)
        if image:
            project.cover_image = image
        project.save()


@login_required
@require_GET
def theme_preview(request, theme_slug):
    profile, response = _photographer_onboarding_profile_or_response(request)
    if response:
        return response
    theme = next((item for item in THEME_OPTIONS if item["slug"] == theme_slug), None)
    if not theme:
        return redirect("photographers:onboarding-theme")
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    template = f"photographers/theme_previews/{theme_slug}.html"
    return render(request, template, {"profile": profile, "website": website, "projects": website.projects.all()[:3], "theme": theme, "sample_label": "Sample preview content"})

@login_required
@require_GET
def skip_onboarding(request):
    if request.user.is_client:
        return redirect("clients:setup-dashboard")
    if not request.user.is_photographer:
        return redirect("accounts:post-login-redirect")
    _photographer_profile(request.user)
    return redirect("photographers:setup-dashboard")
