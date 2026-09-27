from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import PhotographerWebsiteProfile
from apps.dashboard.access import access_for
from apps.photographers.forms import PhotographerWebsiteThemeForm
from apps.photographers.themes import THEME_DEFINITIONS, theme_options

from .settings_forms import WorkspaceBusinessSettingsForm
from .views import _dashboard_context


@login_required
@require_http_methods(["GET", "POST"])
def workspace_settings(request):
    access = access_for(request.user, require="settings")
    request.studio_access = access
    request.studio = access.studio
    profile = access.studio
    website, _ = PhotographerWebsiteProfile.objects.get_or_create(photographer_profile=profile)

    if request.method == "POST" and request.POST.get("action") == "activate_theme":
        theme_value = request.POST.get("theme_value", "")
        definition = THEME_DEFINITIONS.get(theme_value)
        if not definition:
            messages.error(request, "Choose a valid website design.")
            return redirect("photographer_workspace:settings")

        if theme_value == profile.website_theme:
            messages.info(request, f"{definition['name']} is already your active website design.")
            return redirect("photographer_workspace:settings")

        data = QueryDict(mutable=True)
        data["website_theme"] = theme_value
        sections = list(definition["sections"])
        data.setlist("website_sections", sections)
        data["section_order"] = ",".join(sections)
        theme_form = PhotographerWebsiteThemeForm(
            data,
            instance=profile,
            website_profile=website,
            draft=True,
        )
        if theme_form.is_valid():
            with transaction.atomic():
                theme_form.save_structure()
            messages.success(
                request,
                f"{definition['name']} is now your website design. Your saved website content was kept.",
            )
        else:
            messages.error(request, "We could not change the website design. Please try again.")
        return redirect("photographer_workspace:settings")

    form = WorkspaceBusinessSettingsForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
    )
    if request.method == "POST" and request.POST.get("action") == "save_business" and form.is_valid():
        form.save()
        messages.success(request, "Workspace settings saved.")
        return redirect("photographer_workspace:settings")

    themes = []
    for theme in theme_options():
        themes.append({
            **theme,
            "active": theme["value"] == profile.website_theme,
            "preview_url": reverse("photographers:theme-preview", args=[theme["slug"]]),
        })

    current_theme = next((theme for theme in themes if theme["active"]), themes[0] if themes else None)
    context = _dashboard_context(request, "settings", "Settings")
    context.update({
        "form": form,
        "profile": profile,
        "website": website,
        "themes": themes,
        "current_theme": current_theme,
        "website_builder_url": reverse("photographers:website-builder"),
        "website_content_url": reverse("photographers:website-content"),
        "notifications_url": reverse("photographer_workspace:notifications"),
        "financial_url": reverse("photographer_workspace:financial_overview"),
        "galleries_url": reverse("photographer_workspace:galleries"),
        "team_url": reverse("photographer_workspace:team_overview"),
    })
    return render(request, "photographer_workspace/settings/index.html", context)
