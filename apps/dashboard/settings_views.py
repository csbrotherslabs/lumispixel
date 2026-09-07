from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import PhotographerWebsiteProfile
from apps.photographers.forms import PhotographerWebsiteThemeForm
from apps.photographers.themes import THEME_DEFINITIONS, theme_options

from .views import _dashboard_context, photographer_workspace_required


def _require_settings_access(request):
    if not request.studio_access.allows("financials"):
        raise PermissionDenied


@photographer_workspace_required
@require_GET
def photographer_settings(request):
    _require_settings_access(request)
    profile = request.studio
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    themes = []
    for option in theme_options():
        item = dict(option)
        item["is_current"] = option["value"] == profile.website_theme
        item["preview_url"] = reverse("photographers:theme-preview", args=[option["slug"]])
        themes.append(item)

    context = _dashboard_context(request, active_key="settings", title="Settings")
    context.update({
        "website": website,
        "website_themes": themes,
        "current_theme": next((theme for theme in themes if theme["is_current"]), themes[0] if themes else None),
    })
    return render(request, "photographer_workspace/settings.html", context)


@photographer_workspace_required
@require_POST
def switch_website_theme(request):
    _require_settings_access(request)
    profile = request.studio
    requested_theme = request.POST.get("website_theme", "").strip()
    definition = THEME_DEFINITIONS.get(requested_theme)
    if not definition:
        messages.error(request, "That website design is not available.")
        return redirect("photographer_workspace:settings")

    if requested_theme == profile.website_theme:
        messages.info(request, f"{definition['name']} is already your active website design.")
        return redirect("photographer_workspace:settings")

    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)
    default_sections = list(definition["sections"])
    form = PhotographerWebsiteThemeForm(
        data={
            "website_theme": requested_theme,
            "website_sections": default_sections,
            "section_order": ",".join(default_sections),
        },
        instance=profile,
        website_profile=website,
        draft=True,
    )

    if not form.is_valid():
        messages.error(request, "We could not switch the website design. Please preview it and try again.")
        return redirect("photographer_workspace:settings")

    with transaction.atomic():
        form.save_structure()

    messages.success(
        request,
        f"Your website now uses {definition['name']}. Your saved website content was kept; the visible sections were updated for the new design.",
    )
    return redirect("photographer_workspace:settings")
