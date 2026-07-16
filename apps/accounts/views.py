from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .decorators import safe_next_url
from .forms import EmailAuthenticationForm
from .models import User


def _post_login_url(request, next_url=""):
    url = reverse("accounts:post-login-redirect")
    safe = safe_next_url(request, next_url)
    return f"{url}?next={safe}" if safe else url


@require_http_methods(["GET", "POST"])
def login_view(request):
    raw_next = request.POST.get("next") or request.GET.get("next") or ""
    next_url = safe_next_url(request, raw_next)
    if request.user.is_authenticated:
        return redirect(_post_login_url(request, next_url))
    form = EmailAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        if not form.cleaned_data.get("remember"):
            request.session.set_expiry(0)
        return redirect(_post_login_url(request, next_url))
    return render(request, "login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:index")


@login_required
def post_login_redirect(request):
    next_url = safe_next_url(request, request.GET.get("next", ""))
    if next_url:
        return redirect(next_url)
    user = request.user
    if user.required_password_reset:
        return redirect("accounts:password-reset-required")
    if not user.email_verified:
        return redirect("accounts:email-verification-required")
    if not user.onboarding_completed:
        if user.primary_role == User.PrimaryRole.PHOTOGRAPHER:
            return redirect("accounts:photographer-onboarding")
    workspace_routes = {
        User.Workspace.CLIENT: "accounts:client-dashboard",
        User.Workspace.PHOTOGRAPHER: "accounts:photographer-dashboard",
        User.Workspace.MARKETPLACE: "accounts:marketplace-dashboard",
        User.Workspace.OPERATIONS: "accounts:operations-dashboard",
    }
    route = workspace_routes.get(user.last_active_workspace)
    if route:
        return redirect(route)
    if user.primary_role == User.PrimaryRole.PHOTOGRAPHER:
        return redirect("accounts:photographer-dashboard")
    return redirect("accounts:client-dashboard")


@login_required
def placeholder_view(request, title):
    return render(request, "accounts/placeholder.html", {"title": title})
