from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, PhotographerWebsiteProfile
from .forms import FIELD_SECTION_MAP, THEME_FIELD_CONFIG, section_required_fields, actual_hero_image, is_sample_hero
from django.core.validators import validate_email, URLValidator
from django.core.exceptions import ValidationError
from .themes import SECTION_LIBRARY, THEME_DEFINITIONS

from .video_links import video_details
from .experience import existing, parse_experience, visible
from .team import existing_team, team_rows

PUBLISHED_KEY = "_published_website"


def publication_errors(profile, website):
    sections = set(website.sections.filter(is_enabled=True).values_list("section_type", flat=True))
    content = website.theme_content or {}
    errors = []
    if not {"hero", "contact"}.issubset(sections):
        errors.append("Hero and Contact sections are required.")
    for key in sorted(section_required_fields(profile.website_theme, sections)):
        if not str(content.get(key) or "").strip():
            errors.append(f"Complete {key.replace('_', ' ')} before publishing.")
    if not actual_hero_image(website):
        errors.append("Upload your own hero photograph.")
    if "services" in sections and not profile.specialties.exists():
        errors.append("Select at least one photography specialty before publishing Services.")
    if "team" in sections and not existing_team(website) and not content.get("team_members"):
        errors.append("Add at least one team member before publishing Team.")
    if "stats" in sections and not visible(existing(website)) and not content.get("experience_highlights"):
        errors.append("Add at least one visible experience highlight or professional engagement.")
    if "portfolio" in sections:
        projects = list(website.projects.filter(is_featured=True))
        if not projects or any(not (p.title.strip() and p.description.strip() and p.cover_image) for p in projects):
            errors.append("Add at least one complete portfolio project with title, description and cover image.")
    if "equipment" in sections:
        items = list(website.equipment_items.filter(is_featured=True))
        if not items or any(not (p.name.strip() and p.description.strip() and p.image) for p in items):
            errors.append("Add at least one complete equipment item with name, benefit and image.")
    if "contact" in sections:
        try:
            validate_email(content.get("contact_email") or "")
        except ValidationError:
            errors.append("Enter a valid public business email.")
    if "films" in sections:
        if not video_details(content.get("featured_video_url") or ""):
            errors.append("Enter a valid YouTube, Vimeo, or HTTPS MP4 film URL.")
    return errors


def snapshot(profile, website):
    sections = list(website.sections.filter(is_enabled=True).values_list("section_type", flat=True))
    sections = [key for key in sections if key != "reviews"] + ["reviews"]
    theme = profile.website_theme
    config = THEME_FIELD_CONFIG[theme]
    allowed = set(config["required"] + config["optional"]) | section_required_fields(theme, sections) | {"availability_window_months", "availability_call_to_action", "services_intro"}
    content = {key: value for key, value in website.theme_content.items()
               if key in allowed and FIELD_SECTION_MAP.get(key) in sections}
    if "team" in sections and website.theme_content.get("team_members"):
        content["team_members"] = website.theme_content["team_members"]
    return {
        "team_profiles": existing_team(website),
        "theme": theme,
        "brand": profile.business_name or profile.display_name,
        "sections": sections,
        "content": content,
        "hero_image": website.hero_image.name if actual_hero_image(website) else "",
        "portrait": profile.profile_photo.name if profile.profile_photo else "",
        "specialties": list(profile.specialties.values_list("name", flat=True)),
        "biography": profile.biography,
        "phone": profile.phone_number,
        "experience": existing(website),
        "notable_clients": (website.theme_content or {}).get("notable_clients", []),
        "projects": [{"title": p.title, "description": p.description,
                      "image": p.cover_image.name if p.cover_image else ""}
                     for p in website.projects.filter(is_featured=True)],
        "equipment": [{"name": p.name, "description": p.description,
                       "image": p.image.name if p.image else ""}
                      for p in website.equipment_items.filter(is_featured=True)],
        "published_at": timezone.now().isoformat(),
    }


@login_required
@require_POST
@transaction.atomic
def publish_website(request):
    website = get_object_or_404(PhotographerWebsiteProfile.objects.select_for_update(),
                                photographer_profile__user=request.user)
    action = request.POST.get("action")
    content = dict(website.theme_content or {})
    if action == "unpublish":
        content.pop(PUBLISHED_KEY, None)
    elif action == "publish":
        errors = publication_errors(website.photographer_profile, website)
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("photographers:website-content")
        data = snapshot(website.photographer_profile, website)
        if not {"hero", "contact"}.issubset(data["sections"]):
            messages.error(request, "Save your website structure before publishing.")
            return redirect("photographers:website-content")
        content[PUBLISHED_KEY] = data
    else:
        return redirect("photographers:website-content")
    website.theme_content = content
    website.save(update_fields=["theme_content", "updated_at"])
    messages.success(request, "Website published." if action == "publish" else "Website unpublished.")
    return redirect("photographers:website-content")


@require_GET
@never_cache
def public_website(request, slug):
    website = get_object_or_404(PhotographerWebsiteProfile.objects.select_related("photographer_profile"),
                                photographer_profile__slug=slug)
    data = (website.theme_content or {}).get(PUBLISHED_KEY)
    if not data or data.get("theme") not in THEME_DEFINITIONS:
        from django.http import Http404
        raise Http404
    return render_website(request, website, data)


@login_required
@require_POST
@never_cache
def studio_preview(request):
    website = get_object_or_404(PhotographerWebsiteProfile.objects.select_related("photographer_profile"),
                                photographer_profile__user=request.user)
    data = snapshot(website.photographer_profile, website)
    allowed = set(THEME_FIELD_CONFIG[data["theme"]]["required"] + THEME_FIELD_CONFIG[data["theme"]]["optional"]) | section_required_fields(data["theme"], data["sections"]) | {"availability_window_months", "availability_call_to_action", "services_intro"}
    for key in allowed:
        if FIELD_SECTION_MAP.get(key) in data["sections"] and key in request.POST:
            data["content"][key] = request.POST[key][:10000]
    if "availability_window_months" in data["content"]:
        value = str(data["content"]["availability_window_months"])
        data["content"]["availability_window_months"] = int(value) if value in {"1", "2", "3", "6"} else 2
    if "services" in data["sections"] and "studio_specialties" in request.POST:
        from .forms import PhotographerSpecialtiesForm
        specialties_form = PhotographerSpecialtiesForm(request.POST, instance=website.photographer_profile)
        if specialties_form.is_valid():
            data["specialties"] = [item.name for item in specialties_form.cleaned_data["specialties"]]
    if "notable_clients" in data["sections"] and "client_indices" in request.POST:
        from .notable_clients import client_rows
        try:
            data["notable_clients"] = client_rows(request, website, preview=True)
        except ValidationError:
            pass
    if "team" in data["sections"] and "team_indices" in request.POST:
        try:
            data["team_profiles"] = team_rows(request, website, preview=True)
        except ValidationError:
            pass
    if "stats" in data["sections"] and "experience_data" in request.POST:
        try:
            data["experience"] = parse_experience(request)
        except ValidationError:
            pass
    data["projects"] = []
    data["equipment"] = []
    projects = {p.display_order: p for p in website.projects.all()}
    equipment = {p.display_order: p for p in website.equipment_items.all()}
    for index in range(3):
        prefix = f"project_{index}_"
        item = projects.get(index)
        title = request.POST.get(prefix + "title", "")[:500]
        description = request.POST.get(prefix + "description", "")[:10000]
        if title or description or request.POST.get(prefix + "pending"):
            data["projects"].append({"title": title, "description": description, "image": item.cover_image.name if item and item.cover_image else "", "preview_index": index})
    for value in request.POST.get("equipment_indices", "").split(",")[:200]:
        if not value.isdigit() or len(value) > 8:
            continue
        index = int(value)
        prefix = f"equipment_{index}_"
        if request.POST.get(prefix + "remove"):
            continue
        item = equipment.get(index)
        name = request.POST.get(prefix + "name", "")[:500]
        description = request.POST.get(prefix + "description", "")[:10000]
        if name or description or request.POST.get(prefix + "pending"):
            data["equipment"].append({"name": name, "description": description, "image": item.image.name if item and item.image else "", "preview_index": index})
    return render_website(request, website, data, draft_preview=True)


def render_website(request, website, data, draft_preview=False):
    data = dict(data)
    data["sections"] = [key for key in data["sections"] if key != "reviews"] + ["reviews"]
    data["content"] = {key: value for key, value in data["content"].items() if key not in {"testimonial_quote", "testimonial_name"}}
    data["content"] = {**{key: "" for cfg in THEME_FIELD_CONFIG.values() for key in cfg["required"] + cfg["optional"]}, **data["content"]}
    def media_url(field, name):
        return field.storage.url(name) if name else ""
    data["hero_url"] = media_url(website.hero_image, data.get("hero_image")) if not is_sample_hero(data.get("hero_image")) else ""
    from apps.accounts.models import PhotographerWebsiteProject, PhotographerWebsiteEquipment
    for key, model, field in (("projects", PhotographerWebsiteProject, "cover_image"),
                              ("equipment", PhotographerWebsiteEquipment, "image")):
        data[key] = [dict(item, image_url=media_url(model._meta.get_field(field), item["image"]))
                     for item in data.get(key, [])]
    data["notable_clients"] = [dict(item, image_url=media_url(website.hero_image, item.get("image")))
                               for item in data.get("notable_clients", []) if item.get("name")]
    data["team_profiles"] = [dict(item, image_url=media_url(website.hero_image, item.get("image"))) for item in data.get("team_profiles", []) if item.get("name") or draft_preview]
    data["portrait_url"] = media_url(PhotographerProfile._meta.get_field("profile_photo"), data.get("portrait"))
    content = data["content"]
    def first(*keys):
        return next((content.get(key) for key in keys if content.get(key)), "")
    data["headline"] = first("hero_heading", "editorial_heading") or data["brand"]
    data["intro"] = first("hero_subheading")
    data["about_heading"] = first("about_heading", "story_heading") or "About the studio"
    data["about"] = first("about_text", "studio_intro", "story_text", "artist_statement") or data.get("biography")
    data["portfolio_heading"] = first("featured_gallery_title", "project_section_heading", "recent_events_heading", "featured_project_title", "featured_event_title") or "Selected work"
    data["portfolio_description"] = first("featured_project_description", "featured_event_description")
    data["contact_heading"] = first("booking_call_to_action", "consultation_call_to_action", "contact_call_to_action", "contact_statement") or "Let's create something together."
    data["film_url"] = first("featured_video_url", "highlight_video", "hero_video")
    from urllib.parse import urlsplit
    try:
        if urlsplit(data["film_url"]).scheme not in ("https", "http") or not urlsplit(data["film_url"]).hostname:
            data["film_url"] = ""
    except ValueError:
        data["film_url"] = ""
    data["film"] = video_details(data["film_url"])
    supported = {"hero", "contact"}
    if data["about"]:
        supported.add("about")
    if data.get("specialties") or content.get("services_intro"):
        supported.add("services")
    if data["projects"] or data["portfolio_description"]:
        supported.add("portfolio")
    if data["film"]:
        supported.add("films")
    if visible(data.get("experience", {})) or content.get("experience_highlights"):
        supported.add("stats")
    if data["team_profiles"] or content.get("team_members"):
        supported.add("team")
    demo = {}
    if "availability" in data["sections"]:
        from .website_content import public_availability
        demo["availability"] = public_availability(website.photographer_profile, content.get("availability_window_months") or 2)
        demo["availability_call_to_action"] = content.get("availability_call_to_action") or "Request this date"
        supported.add("availability")
    if data["notable_clients"]:
        supported.add("notable_clients")
    if data["equipment"]:
        supported.add("equipment")
    supported.add("reviews")
    sections = [dict(key=key, **SECTION_LIBRARY[key]) for key in data["sections"] if key in supported or draft_preview]
    from apps.marketplace.verified_reviews import review_context
    return render(request, "photographers/public_website.html", {
        **review_context(request, website.photographer_profile, draft_preview),
        "photographer_slug": website.photographer_profile.slug,
        "public_site": True, "draft_preview": draft_preview, "demo": demo, "site": data, "theme": THEME_DEFINITIONS[data["theme"]], "sections": sections,
    })
