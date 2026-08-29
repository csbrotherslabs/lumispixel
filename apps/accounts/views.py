from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .decorators import safe_next_url
from .forms import ClientSignupForm, EmailAuthenticationForm, PhotographerSignupForm
from .models import ClientProfile, PhotographerProfile, User
from .services import (
    EmailDeliveryError,
    create_client_profile,
    create_photographer_workspace,
    email_verification_token,
    normalize_signup_intent,
    send_verification_email,
)

SIGNUP_INTENT_SESSION_KEY = "signup_intent"
AUTH_NEXT_SESSION_KEY = "auth_next_url"
PENDING_USER_SESSION_KEY = "pending_verification_user_id"
VERIFICATION_DELIVERY_SESSION_KEY = "verification_email_delivery_status"


def _post_login_url(request, next_url=""):
    url = reverse("accounts:post-login-redirect")
    safe = safe_next_url(request, next_url)
    return f"{url}?next={safe}" if safe else url


def _store_auth_flow(request, *, intent="general", next_url=""):
    request.session[SIGNUP_INTENT_SESSION_KEY] = normalize_signup_intent(intent)
    safe = safe_next_url(request, next_url)
    if safe:
        request.session[AUTH_NEXT_SESSION_KEY] = safe
    else:
        request.session.pop(AUTH_NEXT_SESSION_KEY, None)
    return safe


def _pending_user(request):
    if request.user.is_authenticated:
        return request.user
    user_id = request.session.get(PENDING_USER_SESSION_KEY)
    if not user_id:
        return None
    return User.objects.filter(pk=user_id).first()


def _remember_pending_user(request, user):
    request.session[PENDING_USER_SESSION_KEY] = str(user.pk)


def _set_verification_delivery_status(request, status):
    request.session[VERIFICATION_DELIVERY_SESSION_KEY] = status


def _clear_auth_flow(request):
    for key in (SIGNUP_INTENT_SESSION_KEY, AUTH_NEXT_SESSION_KEY, PENDING_USER_SESSION_KEY, VERIFICATION_DELIVERY_SESSION_KEY):
        request.session.pop(key, None)


def _is_client_account(user):
    return user.is_client


def _is_photographer_account(user):
    return user.is_photographer


def _client_destination_url(request, user, fallback_route="clients:dashboard"):
    if not user.has_client_profile and not _is_client_account(user):
        return None
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    if not profile.onboarding_completed:
        return reverse("clients:setup-dashboard")
    return reverse(fallback_route)


def _photographer_destination_url(request, user, fallback_route="photographer_workspace:dashboard"):
    # Repair legacy photographer accounts whose profile was not provisioned.
    if not user.has_photographer_profile and _is_photographer_account(user):
        create_photographer_workspace(user)
    if user.has_photographer_profile:
        if not user.photographer_profile.onboarding_completed:
            return reverse("photographers:setup-dashboard")
        return reverse(fallback_route)
    if not user.studio_memberships.filter(status="active").exists():
        return None
    return reverse(fallback_route)


def _authenticated_destination_url(request, user):
    if user.required_password_reset:
        return reverse("accounts:password-reset-required")
    if not user.email_verified:
        _remember_pending_user(request, user)
        return reverse("accounts:email-verification-required")
    if user.last_active_workspace == User.Workspace.PHOTOGRAPHER:
        photographer_destination = _photographer_destination_url(request, user)
        if photographer_destination:
            return photographer_destination
    if user.last_active_workspace == User.Workspace.CLIENT:
        client_destination = _client_destination_url(request, user)
        if client_destination:
            return client_destination
    photographer_destination = _photographer_destination_url(request, user)
    if photographer_destination:
        return photographer_destination
    client_destination = _client_destination_url(request, user)
    if client_destination:
        return client_destination
    workspace_routes = {
        User.Workspace.CLIENT: "clients:dashboard",
        User.Workspace.PHOTOGRAPHER: "photographer_workspace:dashboard",
        User.Workspace.MARKETPLACE: "accounts:marketplace-dashboard",
        User.Workspace.OPERATIONS: "accounts:operations-dashboard",
    }
    route = workspace_routes.get(user.last_active_workspace)
    if route:
        return reverse(route)
    return reverse("accounts:post-login-redirect")


def _post_verification_redirect(request, user):
    next_url = safe_next_url(request, request.session.get(AUTH_NEXT_SESSION_KEY, ""))
    intent = normalize_signup_intent(request.session.get(SIGNUP_INTENT_SESSION_KEY, "general"))
    _clear_auth_flow(request)
    if next_url:
        return next_url
    destination = _authenticated_destination_url(request, user)
    if destination:
        return destination
    client_destination = _client_destination_url(request, user)
    if client_destination:
        return client_destination
    if intent == "marketplace":
        return reverse("accounts:marketplace-request-placeholder")
    return reverse("clients:dashboard")


@require_http_methods(["GET", "POST"])
def login_view(request):
    raw_next = request.POST.get("next") or request.GET.get("next") or ""
    next_url = safe_next_url(request, raw_next)
    if request.user.is_authenticated:
        return redirect(_post_login_url(request, next_url))
    form = EmailAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not user.email_verified:
            _remember_pending_user(request, user)
            _store_auth_flow(request, next_url=next_url, intent=request.session.get(SIGNUP_INTENT_SESSION_KEY, "general"))
            messages.info(request, "Please verify your email address before continuing.")
            return redirect("accounts:verification-pending")
        login(request, user)
        if not form.cleaned_data.get("remember"):
            request.session.set_expiry(0)
        return redirect(_post_login_url(request, next_url))
    return render(request, "login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:index")


@require_GET
def get_started(request):
    safe = _store_auth_flow(request, next_url=request.GET.get("next", ""), intent=request.GET.get("intent", "general"))
    context = {"next": safe}
    if request.user.is_authenticated:
        owned_profile = request.user.photographer_profile if request.user.has_photographer_profile else None
        has_team_membership = request.user.studio_memberships.filter(status="active").exists()
        context.update({
            "has_client_profile": request.user.has_client_profile,
            "owned_photographer_profile": owned_profile,
            "has_team_membership": has_team_membership,
            "photographer_destination": (
                reverse("photographers:setup-dashboard")
                if owned_profile and not owned_profile.onboarding_completed
                else reverse("photographer_workspace:dashboard")
            ) if owned_profile or has_team_membership else "",
        })
    return render(request, "accounts/get_started.html", context)


def _authenticated_signup_redirect(request, account_type):
    next_url = safe_next_url(request, request.GET.get("next", ""))
    if next_url:
        return redirect(next_url)
    return redirect(_authenticated_destination_url(request, request.user))


def _signup_view(request, form_class, template_name, account_type):
    intent = normalize_signup_intent(request.GET.get("intent") or request.POST.get("intent") or "general")
    next_url = _store_auth_flow(request, intent=intent, next_url=request.GET.get("next") or request.POST.get("next") or "")
    if request.user.is_authenticated:
        return _authenticated_signup_redirect(request, account_type)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if user:
            _remember_pending_user(request, user)
            try:
                send_verification_email(request, user)
            except EmailDeliveryError:
                _set_verification_delivery_status(request, "failed")
                messages.warning(request, "We could not send the verification email right now. Please try again.")
            else:
                _set_verification_delivery_status(request, "sent")
                messages.success(request, "We sent a verification email. Please check your inbox to continue.")
            return redirect("accounts:verification-pending")
    return render(request, template_name, {"form": form, "intent": intent, "next": next_url})


@require_http_methods(["GET", "POST"])
def client_signup(request):
    return _signup_view(request, ClientSignupForm, "accounts/signup_client.html", "client")


@require_http_methods(["GET", "POST"])
def photographer_signup(request):
    raw_next = request.GET.get("next") or request.POST.get("next") or ""
    invitation_next = safe_next_url(request, raw_next)
    try:
        is_team_invitation = resolve(invitation_next).view_name == "photographer_workspace:invitation_accept"
    except Resolver404:
        is_team_invitation = False
    if is_team_invitation:
        return _signup_view(request, ClientSignupForm, "accounts/signup_client.html", "client")
    return _signup_view(request, PhotographerSignupForm, "accounts/signup_photographer.html", "photographer")


@require_GET
def verification_pending(request):
    user = _pending_user(request)
    email = user.email if user else ""
    is_verified = bool(user and user.email_verified)
    delivery_status = request.session.get(VERIFICATION_DELIVERY_SESSION_KEY, "unknown")
    return render(
        request,
        "accounts/verification_pending.html",
        {
            "pending_email": email,
            "is_verified": is_verified,
            "can_resend": bool(user and not is_verified),
            "continue_url": _authenticated_destination_url(request, user) if is_verified else "",
            "delivery_status": delivery_status,
        },
    )


@require_GET
def verify_email(request, uidb64, token):
    user = None
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user and user.email_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect(_post_verification_redirect(request, user))
    if user and email_verification_token.check_token(user, token):
        user.mark_email_verified()
        login(request, user)
        messages.success(request, "Your email address has been verified.")
        return redirect(_post_verification_redirect(request, user))
    return render(request, "accounts/verification_result.html", {"success": False}, status=400)


@require_POST
def resend_verification(request):
    user = _pending_user(request)
    if user and not user.email_verified:
        key = f"email-verification-resend:{user.pk}"
        if not cache.get(key):
            try:
                send_verification_email(request, user)
            except EmailDeliveryError:
                _set_verification_delivery_status(request, "failed")
                messages.warning(request, "We could not send the verification email right now. Please try again.")
            else:
                _set_verification_delivery_status(request, "sent")
                cache.set(key, True, 60)
                messages.success(request, "A new verification email was sent.")
        else:
            messages.info(request, "A verification email was sent recently. Please wait a minute before trying again.")
    return redirect("accounts:verification-pending")


@login_required
def post_login_redirect(request):
    next_url = safe_next_url(request, request.GET.get("next", ""))
    if next_url:
        return redirect(next_url)
    return redirect(_authenticated_destination_url(request, request.user))


@login_required
def photographer_onboarding_entry(request):
    return redirect(_authenticated_destination_url(request, request.user))


@login_required
@require_POST
def enable_photographer_workspace(request):
    profile, _ = create_photographer_workspace(request.user)
    if profile.onboarding_completed:
        return redirect("photographer_workspace:dashboard")
    return redirect("photographers:setup-dashboard")


@login_required
@require_POST
def enable_client_profile(request):
    profile, _ = create_client_profile(request.user)
    if profile.onboarding_completed:
        return redirect("clients:dashboard")
    return redirect("clients:setup-dashboard")


@login_required
def client_dashboard(request):
    client_destination = _client_destination_url(request, request.user)
    if client_destination and client_destination != request.path:
        return redirect(client_destination)
    return redirect("clients:dashboard")


@login_required
def placeholder_view(request, title):
    return render(request, "accounts/placeholder.html", {"title": title})
