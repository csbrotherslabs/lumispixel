from decimal import Decimal

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.models import PhotographerProfile, User

WORKSPACE_MODULES = [
    {"key": "dashboard", "url_name": "dashboard", "icon": "bi-grid-1x2", "title": "Dashboard", "description": "Your business command center.", "coming_soon": False},
    {"key": "galleries", "url_name": "galleries", "icon": "bi-images", "title": "Galleries", "description": "Organize, publish, and deliver photography collections.", "coming_soon": True, "planned": ["Gallery organization", "Publishing controls", "Client delivery"]},
    {"key": "clients", "url_name": "clients", "icon": "bi-people", "title": "Clients", "description": "Manage client relationships, invitations, and gallery access.", "coming_soon": True, "planned": ["Client records", "Invitations", "Gallery access"]},
    {"key": "events", "url_name": "events", "icon": "bi-calendar-event", "title": "Events", "description": "Manage photography events and event-code photo discovery.", "coming_soon": True, "planned": ["Event setup", "Event codes", "Photo discovery"]},
    {"key": "ai", "url_name": "ai", "icon": "bi-stars", "title": "AI Workspace", "description": "Future home for culling, editing assistance, search, tagging, and face recognition.", "coming_soon": True, "planned": ["Face recognition", "Image quality scoring", "Duplicate detection", "Blur detection", "Semantic search", "Auto-tagging", "AI editing assistance", "Watermark generation"]},
    {"key": "website", "url_name": "website", "icon": "bi-window", "title": "Client Website", "description": "Manage the photographer’s customer-facing homepage and branding.", "coming_soon": True, "planned": ["Brand preview", "Homepage sections", "Theme settings"]},
    {"key": "marketplace", "url_name": "marketplace", "icon": "bi-shop", "title": "Marketplace", "description": "Discover and sell products, services, or photography-related offerings.", "coming_soon": True, "planned": ["Offer listings", "Product discovery", "Sales channels"]},
    {"key": "orders", "url_name": "orders", "icon": "bi-bag-check", "title": "Orders", "description": "Track downloads, print purchases, and customer orders.", "coming_soon": True, "planned": ["Order history", "Print purchases", "Download tracking"]},
    {"key": "billing", "url_name": "billing", "icon": "bi-credit-card", "title": "Billing", "description": "Manage LumisPixel subscription and payment configuration.", "coming_soon": True, "planned": ["Subscription settings", "Payment configuration", "Invoices"]},
    {"key": "analytics", "url_name": "analytics", "icon": "bi-graph-up-arrow", "title": "Analytics", "description": "Review gallery activity, client engagement, sales, and business performance.", "coming_soon": True, "planned": ["Gallery activity", "Client engagement", "Business performance"]},
    {"key": "marketing", "url_name": "marketing", "icon": "bi-megaphone", "title": "Marketing", "description": "Manage promotions, outreach, and future campaign tools.", "coming_soon": True, "planned": ["Promotions", "Outreach", "Campaign tools"]},
    {"key": "profile", "url_name": "profile", "icon": "bi-person-badge", "title": "Profile", "description": "Review photographer and business information.", "coming_soon": False, "planned": ["Business details", "Contact information", "Specialties"]},
    {"key": "settings", "url_name": "settings", "icon": "bi-sliders", "title": "Settings", "description": "Manage workspace preferences, branding, notifications, and future theme switching.", "coming_soon": True, "planned": ["Workspace preferences", "Branding", "Notifications", "Future theme switching"]},
]
WORKSPACE_MODULES += [
    {"key": key, "url_name": key, "icon": "", "title": title, "description": f"{title} tools for your photography business are being prepared.", "coming_soon": True}
    for key, title in [
        ("crm", "CRM"), ("leads", "Leads"), ("ai_search", "AI Search"), ("albums", "Albums"),
        ("calendar", "Calendar"), ("bookings", "Bookings"), ("contracts", "Contracts"),
        ("invoices", "Invoices"), ("payments", "Payments"), ("revenue", "Revenue"),
        ("reviews", "Reviews"), ("referrals", "Referrals"), ("workflows", "Workflows"),
        ("ai_assistant", "AI Assistant"), ("team", "Team"), ("equipment", "Equipment"),
        ("tasks", "Tasks"), ("notifications", "Notifications"), ("help", "Help"),
    ]
]
MODULE_BY_KEY = {m["key"]: m for m in WORKSPACE_MODULES}

NAVIGATION = [
    {"title": "", "icon": "bi-speedometer2", "items": [("dashboard", "Dashboard", "bi-grid-1x2")]},
    {"title": "Clients", "icon": "bi-people", "items": [("crm", "CRM", "bi-person-lines-fill"), ("leads", "Leads", "bi-person-plus"), ("clients", "Clients", "bi-people-fill")]},
    {"title": "Galleries", "icon": "bi-images", "items": [("galleries", "Galleries", "bi-images"), ("ai_search", "AI Search", "bi-stars"), ("albums", "Albums", "bi-collection")]},
    {"title": "Bookings", "icon": "bi-calendar-check", "items": [("calendar", "Calendar", "bi-calendar3"), ("bookings", "Bookings", "bi-calendar-check"), ("contracts", "Contracts", "bi-file-earmark-text")]},
    {"title": "Financial", "icon": "bi-wallet2", "items": [("invoices", "Invoices", "bi-receipt"), ("payments", "Payments", "bi-credit-card"), ("revenue", "Revenue", "bi-graph-up-arrow")]},
    {"title": "Business Growth", "icon": "bi-rocket-takeoff", "items": [("marketing", "Marketing", "bi-megaphone"), ("reviews", "Reviews", "bi-star"), ("referrals", "Referrals", "bi-share")]},
    {"title": "Automation", "icon": "bi-lightning-charge", "items": [("workflows", "Workflows", "bi-diagram-3"), ("ai_assistant", "AI Assistant", "bi-chat-dots") ]},
    {"title": "Operations", "icon": "bi-briefcase", "items": [("team", "Team", "bi-person-workspace"), ("equipment", "Equipment", "bi-camera"), ("tasks", "Tasks", "bi-check2-square") ]},
    {"title": "Reports", "icon": "bi-bar-chart", "items": [("analytics", "Analytics", "bi-bar-chart-line")]},
    {"title": "", "icon": "bi-grid", "items": [("marketplace", "Marketplace", "bi-shop"), ("settings", "Settings", "bi-gear")]},
]
THEMES = {
    PhotographerProfile.WebsiteTheme.ELEGANT: ("Elegant", "A refined visual direction for weddings, portraits, family, and fine-art work.", "elegant"),
    PhotographerProfile.WebsiteTheme.MODERN_STUDIO: ("Modern Studio", "A clean studio presentation for commercial, branding, product, and headshot work.", "modern"),
    PhotographerProfile.WebsiteTheme.SPORTS_EVENTS: ("Sports & Events", "A high-energy direction for sports, schools, events, and high-volume photography.", "sports"),
}


def _reverse_module(module):
    return reverse(f"photographer_workspace:{module['url_name']}")


def _workspace_nav(active_key):
    groups = []
    for index, group in enumerate(NAVIGATION):
        items = []
        for key, title, icon in group["items"]:
            module = MODULE_BY_KEY[key]
            items.append({"key": key, "title": title, "icon": icon, "url": _reverse_module(module), "active": key == active_key})
        groups.append({"title": group["title"], "icon": group["icon"], "id": f"nav-group-{index}", "items": items, "expanded": not group["title"] or any(item["active"] for item in items), "active": any(item["active"] for item in items)})
    return groups


def _photographer_workspace_response(request):
    user = request.user
    if not user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    if user.is_staff and not user.is_photographer:
        return None
    if user.primary_role == User.PrimaryRole.CLIENT:
        return redirect("clients:dashboard")
    if user.primary_role != User.PrimaryRole.PHOTOGRAPHER:
        return redirect("accounts:post-login-redirect")
    profile, _ = PhotographerProfile.objects.get_or_create(user=user)
    if not profile.onboarding_completed:
        return redirect("photographers:setup-dashboard")
    return None


def photographer_workspace_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        response = _photographer_workspace_response(request)
        if response:
            return response
        return view_func(request, *args, **kwargs)
    return wrapped


def _identity(profile, user):
    name = user.full_name or profile.display_name or user.email
    initials = "".join(part[:1] for part in name.split()[:2]).upper() or "LP"
    photo = profile.profile_photo.url if profile.profile_photo else ""
    return {"name": name, "initials": initials, "image_url": photo, "image_alt": f"{name} profile photo" if photo else ""}


def _theme(profile):
    name, description, preview = THEMES.get(profile.website_theme, THEMES[PhotographerProfile.WebsiteTheme.ELEGANT])
    return {"name": name, "description": description, "preview_class": preview}


def _count_model(app_label, model_name, filters=None):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return 0, False
    if not model:
        return 0, False
    try:
        return model.objects.filter(**(filters or {})).count(), True
    except Exception:
        return 0, False


def _business_overview(profile):
    galleries, galleries_real = _count_model("galleries", "Gallery", {"photographer": profile})
    photos, photos_real = _count_model("galleries", "Photo", {"gallery__photographer": profile})
    orders, orders_real = _count_model("marketplace", "Order", {"photographer": profile})
    return [
        {"icon": "bi-images", "metric": galleries, "label": "Total Galleries", "note": "No gallery model data yet." if not galleries_real else "From gallery records.", "url": reverse("photographer_workspace:galleries")},
        {"icon": "bi-camera", "metric": photos, "label": "Total Photos", "note": "No photo model data yet." if not photos_real else "From photo records.", "url": reverse("photographer_workspace:galleries")},
        {"icon": "bi-people", "metric": 0, "label": "Clients", "note": "No photographer-client relationship model yet.", "url": reverse("photographer_workspace:clients")},
        {"icon": "bi-bag-check", "metric": orders, "label": "Orders", "note": "No order model data yet." if not orders_real else "From order records.", "url": reverse("photographer_workspace:orders")},
        {"icon": "bi-currency-dollar", "metric": f"{profile.default_currency} {Decimal('0.00')}", "label": "Revenue", "note": "Revenue tracking is not connected yet.", "url": reverse("photographer_workspace:billing")},
    ]


def _dashboard_context(request, active_key="dashboard", title="Dashboard"):
    profile = request.user.photographer_profile
    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    modules = [m | {"url": _reverse_module(m)} for m in WORKSPACE_MODULES if m["key"] != "dashboard"]
    context = {
        "active_key": active_key, "page_title": title, "workspace_nav": _workspace_nav(active_key),
        "photographer_profile": profile, "identity": _identity(profile, request.user), "greeting": greeting,
        "welcome_name": profile.business_name or profile.display_name or request.user.full_name or "Photographer",
        "modules": modules, "theme_preview": _theme(profile), "overview_cards": _business_overview(profile),
        "getting_started": [
            {"label": "Business profile completed", "done": bool(profile.business_name or profile.display_name), "url": reverse("photographer_workspace:profile")},
            {"label": "Client website theme selected", "done": profile.website_theme in THEMES, "url": reverse("photographer_workspace:website")},
            {"label": "Upload first photos", "done": False, "url": reverse("photographer_workspace:galleries")},
            {"label": "Create first gallery", "done": False, "url": reverse("photographer_workspace:galleries")},
            {"label": "Invite first client", "done": False, "url": reverse("photographer_workspace:clients")},
            {"label": "Connect payments", "done": False, "url": reverse("photographer_workspace:billing")},
        ],
    }
    return context


@photographer_workspace_required
@require_GET
def photographer_dashboard(request):
    return render(request, "photographer_workspace/dashboard.html", _dashboard_context(request))


@photographer_workspace_required
@require_GET
def module_placeholder(request, module_key):
    module = MODULE_BY_KEY[module_key]
    context = _dashboard_context(request, module_key, module["title"])
    context["module"] = module | {"url": _reverse_module(module)}
    return render(request, "photographer_workspace/placeholder.html", context)
