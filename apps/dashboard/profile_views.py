from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.dashboard.access import access_for
from apps.dashboard.profile_forms import PhotographerPersonalProfileForm


def _initials(name):
    return "".join(part[:1] for part in name.split()[:2]).upper() or "LP"


@login_required
@require_http_methods(["GET", "POST"])
def photographer_profile(request):
    """Person-level profile shared across the user's LumisPixel contexts."""
    if not request.user.can_login or not request.user.can_use_photographer_workspace:
        return redirect("accounts:post-login-redirect")

    access = access_for(request.user)
    studio = access.studio
    membership = access.membership
    form = PhotographerPersonalProfileForm(request.POST or None, instance=request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("photographer_workspace:profile")

    name = request.user.full_name or request.user.email
    owned_studio = getattr(request.user, "photographer_profile", None)
    memberships = request.user.studio_memberships.select_related("studio").filter(
        status="active"
    ).order_by("studio__business_name", "studio__display_name")
    contexts = []
    if request.user.has_client_profile:
        contexts.append({"label": "Personal photo space", "kind": "Client", "icon": "bi-images"})
    if owned_studio:
        contexts.append({"label": owned_studio.business_name or owned_studio.display_name or "My photography business", "kind": "Owner", "icon": "bi-building"})
    for item in memberships:
        contexts.append({"label": item.studio.business_name or item.studio.display_name or "Photography studio", "kind": item.get_role_display(), "icon": "bi-people"})

    # Existing profile photos remain workspace/business media until the shared
    # person-level avatar is migrated to User in a future schema change.
    image_url = ""
    if owned_studio and owned_studio.profile_photo:
        image_url = owned_studio.profile_photo.url
    elif membership and membership.studio.profile_photo:
        image_url = membership.studio.profile_photo.url

    return render(request, "photographer_workspace/profile.html", {
        "page_title": "My Profile",
        "hide_topbar_heading": True,
        "identity": {"name": name, "initials": _initials(name), "image_url": image_url, "image_alt": f"{name} profile photo" if image_url else ""},
        "form": form,
        "profile_user": request.user,
        "current_access": access,
        "current_studio": studio,
        "contexts": contexts,
        "workspace_nav": [],
        "settings_url": reverse("photographer_workspace:settings"),
        "has_owned_studio": bool(owned_studio),
        "account_status_label": User.AccountStatus(request.user.account_status).label,
    })
