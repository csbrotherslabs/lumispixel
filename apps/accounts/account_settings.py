from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.clients.forms import ClientOnboardingProfileForm

from .models import ClientProfile


@login_required
@require_http_methods(["GET", "POST"])
def account_settings(request):
    """Person-level settings shared by every LumisPixel role/context."""
    user = request.user
    if not user.can_login:
        return redirect("accounts:post-login-redirect")

    # ClientProfile currently owns the personal photo/location/preferences fields.
    # Reuse it as a compatibility store even for photographer-only accounts while
    # User remains authoritative for the person's name and sign-in identity.
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    form = ClientOnboardingProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        user=user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('accounts:account-settings')}?saved=1")

    return render(request, "accounts/account_settings.html", {
        "form": form,
        "profile": profile,
        "saved": request.GET.get("saved") == "1",
        "back_url": reverse("accounts:post-login-redirect"),
        "workspace_settings_url": reverse("photographer_workspace:settings") if user.can_use_photographer_workspace else "",
    })
