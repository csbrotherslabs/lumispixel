from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, PhotographerWebsiteProfile
from .forms import FIELD_SECTION_MAP, THEME_FIELD_CONFIG
from .themes import SECTION_LIBRARY, THEME_DEFINITIONS

PUBLISHED_KEY = "_published_website"


def snapshot(profile, website):
    sections = list(website.sections.filter(is_enabled=True).values_list("section_type", flat=True))
    theme = profile.website_theme
    config = THEME_FIELD_CONFIG[theme]
    allowed = set(config["required"] + config["optional"])
    content = {key: value for key, value in website.theme_content.items()
               if key in allowed and FIELD_SECTION_MAP.get(key) in sections}
    return {
        "theme": theme,
        "brand": profile.business_name or profile.display_name,
        "sections": sections,
        "content": content,
        "hero_image": website.hero_image.name if website.hero_image else "",
        "specialties": list(profile.specialties.values_list("name", flat=True)),
        "biography": profile.biography,
        "phone": profile.phone_number,
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
    data = dict(data)
    data["content"] = {**{key: "" for cfg in THEME_FIELD_CONFIG.values() for key in cfg["required"] + cfg["optional"]}, **data["content"]}
    def media_url(field, name):
        return field.storage.url(name) if name else ""
    data["hero_url"] = media_url(website.hero_image, data.get("hero_image"))
    from apps.accounts.models import PhotographerWebsiteProject, PhotographerWebsiteEquipment
    for key, model, field in (("projects", PhotographerWebsiteProject, "cover_image"),
                              ("equipment", PhotographerWebsiteEquipment, "image")):
        data[key] = [dict(item, image_url=media_url(model._meta.get_field(field), item["image"]))
                     for item in data.get(key, [])]
    supported = {"hero", "about", "services", "portfolio", "contact"}
    if data["equipment"]:
        supported.add("equipment")
    if data["content"].get("testimonial_quote"):
        supported.add("reviews")
    sections = [dict(key=key, **SECTION_LIBRARY[key]) for key in data["sections"] if key in supported]
    return render(request, "photographers/public_website.html", {
        "site": data, "theme": THEME_DEFINITIONS[data["theme"]], "sections": sections,
    })
