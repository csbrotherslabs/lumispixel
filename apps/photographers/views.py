from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import PhotographerProfile, PhotographerWebsiteEquipment, PhotographerWebsiteProfile, PhotographerWebsiteProject
from apps.accounts.onboarding import get_photographer_onboarding_resume_url
from apps.accounts.views import _authenticated_destination_url

from .forms import FIELD_SECTION_MAP, PhotographerBusinessPreferencesForm, PhotographerOnboardingProfileForm, PhotographerSpecialtiesForm, PhotographerWebsiteThemeForm, THEME_FIELD_CONFIG, IMAGE_TYPES, MAX_IMAGE_SIZE
from .themes import SECTION_LIBRARY, THEME_DEFINITIONS, section_options, theme_by_slug, theme_options
from .website_content import preview_content

THEME_OPTIONS = theme_options()
PHOTOGRAPHER_TOTAL_STEPS = 5
SELECTED_THEME_PREVIEW_SESSION_KEY = "photographer_selected_theme_preview"


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
    builder_mode = request.resolver_match.url_name == "website-builder"
    if not request.user.has_photographer_profile:
        destination = "clients:setup-dashboard" if request.user.has_client_profile else _authenticated_destination_url(request, request.user)
        return redirect(destination)
    profile = _photographer_profile(request.user)
    if profile.onboarding_completed and not builder_mode:
        return redirect("photographer_workspace:dashboard")
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    action = request.POST.get("action", "continue_to_content") if request.method == "POST" else None
    preview_state = request.session.get(SELECTED_THEME_PREVIEW_SESSION_KEY) if request.method == "GET" and request.GET.get("restore_preview") == "1" else None
    preview_initial = None
    if preview_state:
        preview_initial = {
            "website_theme": preview_state["theme_value"],
            "website_sections": preview_state["sections"],
            "section_order": ",".join(preview_state["sections"]),
        }
    form = PhotographerWebsiteThemeForm(request.POST or None, instance=profile, website_profile=website, draft=True, initial=preview_initial)
    if request.method == "POST" and form.is_valid():
        profile, website = form.save_structure()
        request.session.pop(SELECTED_THEME_PREVIEW_SESSION_KEY, None)
        if action == "save_structure_draft" and not builder_mode:
            messages.success(request, "Your website structure has been saved. You can add content anytime.")
            return redirect("photographers:setup-dashboard")
        messages.success(request, "Your website structure is ready. Now add the content for your selected sections.")
        return redirect("photographers:website-content" if builder_mode else "photographers:onboarding-website-content")
    selected_sections = set(form["website_sections"].value() or [])
    return render(request, "photographers/onboarding_theme.html", _context(5, "photographer-onboarding-theme-title", form=form, profile=profile, website=website, theme_options=THEME_OPTIONS, section_options=section_options(), selected_sections=selected_sections, builder_mode=builder_mode))


@login_required
@require_http_methods(["GET", "POST"])
def website_content(request):
    builder_mode = request.resolver_match.url_name == "website-content"
    if not request.user.has_photographer_profile:
        destination = "clients:setup-dashboard" if request.user.has_client_profile else _authenticated_destination_url(request, request.user)
        return redirect(destination)
    profile = _photographer_profile(request.user)
    if profile.onboarding_completed and not builder_mode:
        return redirect("photographer_workspace:dashboard")
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    selected_sections = list(website.sections.filter(is_enabled=True).order_by("display_order", "id").values_list("section_type", flat=True))
    if not selected_sections:
        messages.info(request, "Choose a template and sections before adding website content.")
        return redirect("photographers:website-builder" if builder_mode else "photographers:onboarding-theme")
    action = request.POST.get("action", "save_content" if builder_mode else "finish_setup") if request.method == "POST" else None
    form = PhotographerWebsiteThemeForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        website_profile=website,
        draft=action in {"save_draft", "save_content"},
        content_only=True,
    )
    if request.method == "POST" and form.is_valid():
        equipment_error = _equipment_upload_error(request, website) if "equipment" in selected_sections else None
        if equipment_error:
            form.add_error(None, equipment_error)
        else:
            profile, website = form.save_content()
            _save_project_drafts(request, website)
            if "equipment" in selected_sections:
                _save_equipment_drafts(request, website)
            if builder_mode:
                messages.success(request, "Your website content has been saved.")
                return redirect("photographers:website-content")
            if action == "save_draft":
                messages.success(request, "Your website content draft has been saved.")
                return redirect("photographers:setup-dashboard")
            profile.onboarding_completed = True
            profile.onboarding_step = PHOTOGRAPHER_TOTAL_STEPS
            profile.save(update_fields=["onboarding_completed", "onboarding_step", "updated_at"])
            return redirect("photographer_workspace:dashboard")
    panels = _section_content_panels(form, profile.website_theme, selected_sections)
    equipment_slots = _equipment_slots(website)
    return render(request, "photographers/onboarding_website_content.html", _context(
        5,
        "photographer-onboarding-content-title",
        form=form,
        profile=profile,
        website=website,
        projects=list(website.projects.all()[:3]),
        panels=panels,
        equipment_slots=equipment_slots,
        equipment_indices=",".join(str(slot["index"]) for slot in equipment_slots),
        next_equipment_index=_next_equipment_index(website),
        selected_sections=selected_sections,
        builder_mode=builder_mode,
    ))


def _section_content_panels(form, theme, selected_sections):
    allowed = set(THEME_FIELD_CONFIG[theme]["required"] + THEME_FIELD_CONFIG[theme]["optional"])
    allowed.update(("hero_image", "availability_window_months", "availability_call_to_action"))
    panels = []
    for section_key in selected_sections:
        field_names = [name for name in form.fields if name in allowed and FIELD_SECTION_MAP.get(name) == section_key]
        panels.append({
            "key": section_key,
            "name": SECTION_LIBRARY[section_key]["name"],
            "description": SECTION_LIBRARY[section_key]["description"],
            "fields": [form[name] for name in field_names],
            "supports_projects": section_key == "portfolio" and theme == PhotographerProfile.WebsiteTheme.PORTFOLIO_EDITORIAL,
            "supports_equipment": section_key == "equipment",
        })
    return panels


def _equipment_slots(website):
    items = list(website.equipment_items.all())
    if items:
        return [{"index": item.display_order, "item": item} for item in items]
    return [{"index": 0, "item": None}]


def _next_equipment_index(website):
    last = website.equipment_items.order_by("-display_order").values_list("display_order", flat=True).first()
    return (last + 1) if last is not None else 1


def _posted_equipment_indices(request):
    indices = []
    for value in request.POST.get("equipment_indices", "").split(","):
        value = value.strip()
        if value.isdigit() and int(value) not in indices:
            indices.append(int(value))
    return indices[:200]


def _equipment_upload_error(request, website):
    existing = {item.display_order: item for item in website.equipment_items.all()}
    for position, index in enumerate(_posted_equipment_indices(request), start=1):
        if request.POST.get(f"equipment_{index}_remove"):
            continue
        name = request.POST.get(f"equipment_{index}_name", "").strip()
        description = request.POST.get(f"equipment_{index}_description", "").strip()
        image = request.FILES.get(f"equipment_{index}_image")
        if not (name or description or image):
            continue
        if not name:
            return f"Equipment item {position} needs a name."
        if index not in existing and not image:
            return f"Equipment item {position} needs an image."
        if image and image.content_type not in IMAGE_TYPES:
            return f"Equipment item {position} must use a JPG, PNG, GIF, or WebP image."
        if image and image.size > MAX_IMAGE_SIZE:
            return f"Equipment item {position} must be 5 MB or smaller."
    return None


def _save_equipment_drafts(request, website):
    existing = {item.display_order: item for item in website.equipment_items.all()}
    for index in _posted_equipment_indices(request):
        item = existing.get(index)
        if request.POST.get(f"equipment_{index}_remove"):
            if item:
                item.image.delete(save=False)
                item.delete()
            continue
        name = request.POST.get(f"equipment_{index}_name", "").strip()
        description = request.POST.get(f"equipment_{index}_description", "").strip()
        image = request.FILES.get(f"equipment_{index}_image")
        if not (name or description or image):
            continue
        old_image = item.image.name if item and item.image else None
        item = item or PhotographerWebsiteEquipment(photographer_website=website, display_order=index)
        item.name = name
        item.description = description
        if image:
            item.image = image
        item.is_featured = True
        item.save()
        if image and old_image and old_image != item.image.name:
            item.image.storage.delete(old_image)


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
    if not request.user.has_photographer_profile:
        destination = "clients:setup-dashboard" if request.user.has_client_profile else _authenticated_destination_url(request, request.user)
        return redirect(destination)
    profile = _photographer_profile(request.user)
    theme = theme_by_slug(theme_slug)
    if not theme:
        return redirect("photographers:onboarding-theme")
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    sections = [dict(key=key, **SECTION_LIBRARY[key]) for key in theme["sections"]]
    return render(request, theme["preview_template"], {"profile": profile, "website": website, "projects": website.projects.all()[:3], "theme": theme, "sections": sections, "demo": preview_content(profile, website), "sample_label": "Completed theme preview"})


@login_required
@require_http_methods(["GET", "POST"])
def selected_theme_preview(request):
    if not request.user.has_photographer_profile:
        destination = "clients:setup-dashboard" if request.user.has_client_profile else _authenticated_destination_url(request, request.user)
        return redirect(destination)

    if request.method == "POST":
        theme_value = request.POST.get("website_theme", "")
        definition = THEME_DEFINITIONS.get(theme_value)
        if not definition:
            messages.error(request, "Choose a template before previewing your selection.")
            return redirect("photographers:onboarding-theme")

        requested_sections = request.POST.getlist("website_sections")
        selected = []
        for key in requested_sections:
            if key in SECTION_LIBRARY and key not in selected:
                selected.append(key)
        for required_section in ("hero", "contact"):
            if required_section not in selected:
                selected.append(required_section)

        requested_order = [key for key in request.POST.get("section_order", "").split(",") if key in selected]
        sections = list(dict.fromkeys(requested_order + selected))
        return_context = "builder" if request.POST.get("preview_context") == "builder" else "onboarding"
        request.session[SELECTED_THEME_PREVIEW_SESSION_KEY] = {
            "theme_value": theme_value,
            "sections": sections,
            "return_context": return_context,
            "content": {
                "availability_window_months": request.POST.get("availability_window_months", "2"),
                "availability_call_to_action": request.POST.get("availability_call_to_action", ""),
                "equipment_inventory": request.POST.get("equipment_inventory", ""),
            },
        }
        return redirect("photographers:selected-theme-preview")

    state = request.session.get(SELECTED_THEME_PREVIEW_SESSION_KEY)
    if not state or state.get("theme_value") not in THEME_DEFINITIONS:
        return redirect("photographers:onboarding-theme")

    profile = _photographer_profile(request.user)
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    definition = THEME_DEFINITIONS[state["theme_value"]]
    theme = dict(value=state["theme_value"], **definition)
    section_keys = [key for key in state.get("sections", []) if key in SECTION_LIBRARY]
    sections = [dict(key=key, **SECTION_LIBRARY[key]) for key in section_keys]
    return_route = "photographers:website-builder" if state.get("return_context") == "builder" else "photographers:onboarding-theme"
    preview_return_url = f"{reverse(return_route)}?restore_preview=1"
    return render(request, theme["preview_template"], {
        "profile": profile,
        "website": website,
        "projects": website.projects.all()[:3],
        "theme": theme,
        "sections": sections,
        "demo": preview_content(profile, website, state.get("content")),
        "sample_label": "Your selected preview",
        "custom_preview": True,
        "preview_return_url": preview_return_url,
    })

@login_required
@require_GET
def skip_onboarding(request):
    if request.user.is_client:
        return redirect("clients:setup-dashboard")
    if not request.user.is_photographer:
        return redirect("accounts:post-login-redirect")
    _photographer_profile(request.user)
    return redirect("photographers:setup-dashboard")
