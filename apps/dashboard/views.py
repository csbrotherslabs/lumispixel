from decimal import Decimal

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead
from apps.clients.forms import ClientTaskForm, CrmClientForm, LeadForm

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


def _dashboard_summary(profile):
    return [
        {"icon": "bi-graph-up-arrow", "metric": f"{profile.default_currency} {Decimal('0.00')}", "label": "Revenue This Month", "note": "No revenue recorded", "url": reverse("photographer_workspace:revenue")},
        {"icon": "bi-calendar-check", "metric": 0, "label": "Upcoming Bookings", "note": "No bookings scheduled", "url": reverse("photographer_workspace:bookings")},
        {"icon": "bi-people", "metric": 0, "label": "Active Clients", "note": "No active clients", "url": reverse("photographer_workspace:clients")},
        {"icon": "bi-hourglass-split", "metric": f"{profile.default_currency} {Decimal('0.00')}", "label": "Pending Payments", "note": "Nothing outstanding", "url": reverse("photographer_workspace:payments")},
    ]


def _dashboard_tools():
    groups = []
    for group in NAVIGATION[1:9]:
        groups.append({
            "title": "Growth" if group["title"] == "Business Growth" else group["title"],
            "icon": group["icon"],
            "items": [
                {"title": title, "icon": icon, "url": _reverse_module(MODULE_BY_KEY[key])}
                for key, title, icon in group["items"]
            ],
        })
    return groups


def _dashboard_context(request, active_key="dashboard", title="Dashboard"):
    profile = request.user.photographer_profile
    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    modules = [m | {"url": _reverse_module(m)} for m in WORKSPACE_MODULES if m["key"] != "dashboard"]
    context = {
        "active_key": active_key, "page_title": title, "workspace_nav": _workspace_nav(active_key),
        "photographer_profile": profile, "identity": _identity(profile, request.user), "greeting": greeting,
        "welcome_name": request.user.first_name or (request.user.full_name.split()[0] if request.user.full_name else "Photographer"),
        "summary_cards": _dashboard_summary(profile),
        "schedule_items": [], "activity_items": [],
        "quick_actions": [
            {"label": "Upload Photos", "icon": "bi-cloud-arrow-up", "url": reverse("photographer_workspace:galleries")},
            {"label": "Create Gallery", "icon": "bi-images", "url": reverse("photographer_workspace:galleries")},
            {"label": "Add Client", "icon": "bi-person-plus", "url": reverse("photographer_workspace:clients")},
            {"label": "Create Booking", "icon": "bi-calendar-plus", "url": reverse("photographer_workspace:bookings")},
            {"label": "Send Invoice", "icon": "bi-send", "url": reverse("photographer_workspace:invoices")},
        ],
        "business_snapshot": [
            {"label": "New Leads", "count": 0, "icon": "bi-person-plus", "summary": "No new inquiries to review.", "action": "View leads", "url": reverse("photographer_workspace:leads")},
            {"label": "Recent Galleries", "count": _count_model("galleries", "Gallery", {"photographer": profile})[0], "icon": "bi-images", "summary": "Your latest client galleries appear here.", "action": "View galleries", "url": reverse("photographer_workspace:galleries")},
            {"label": "Outstanding Invoices", "count": 0, "icon": "bi-receipt", "summary": "You’re all caught up.", "action": "View invoices", "url": reverse("photographer_workspace:invoices")},
            {"label": "Pending Contracts", "count": 0, "icon": "bi-file-earmark-check", "summary": "No contracts await signatures.", "action": "View contracts", "url": reverse("photographer_workspace:contracts")},
        ],
        "tool_groups": _dashboard_tools(),
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
def clients_crm(request):
    profile = request.user.photographer_profile
    today = timezone.localdate()
    now = timezone.now()
    leads = Lead.objects.for_photographer(profile)
    clients = Client.objects.for_photographer(profile)
    pipeline_counts = {row["status"]: row["count"] for row in leads.values("status").annotate(count=Count("id"))}
    pipeline = [
        {"key": key, "label": label, "count": pipeline_counts.get(key, 0),
         "url": f"{reverse('photographer_workspace:leads')}?status={key}"}
        for key, label in Lead.Status.choices
    ]
    balance_expression = ExpressionWrapper(
        F("total") - F("amount_paid"), output_field=DecimalField(max_digits=12, decimal_places=2)
    )
    outstanding = ClientInvoice.objects.for_photographer(profile).exclude(
        status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID]
    ).aggregate(total=Coalesce(Sum(balance_expression), Value(Decimal("0.00")), output_field=DecimalField()))["total"]
    sessions = ClientSession.objects.for_photographer(profile).filter(starts_at__gte=now).exclude(
        status=ClientSession.Status.CANCELLED
    ).select_related("client")
    metrics = [
        ("Total Leads", leads.count(), "bi-person-plus"),
        ("Active Clients", clients.filter(status=Client.Status.ACTIVE).count(), "bi-people"),
        ("New Inquiries", leads.filter(created_at__date__gte=today - timezone.timedelta(days=30)).count(), "bi-envelope-open"),
        ("Awaiting Response", leads.filter(status__in=[Lead.Status.NEW, Lead.Status.CONTACTED]).count(), "bi-reply"),
        ("Upcoming Sessions", sessions.count(), "bi-calendar-event"),
        ("Outstanding Balance", f"{profile.default_currency} {outstanding:,.2f}", "bi-wallet2"),
    ]
    context = _dashboard_context(request, "crm", "Clients")
    context.update({
        "crm_metrics": [{"label": label, "value": value, "icon": icon} for label, value, icon in metrics],
        "pipeline": pipeline,
        "recent_leads": leads.order_by("-created_at")[:8],
        "upcoming_sessions": sessions.order_by("starts_at")[:6],
        "tasks": ClientTask.objects.for_photographer(profile).exclude(
            status__in=[ClientTask.Status.COMPLETED, ClientTask.Status.CANCELLED]
        ).select_related("client", "lead").order_by(F("due_date").asc(nulls_last=True), "-created_at")[:7],
        "recent_activity": ClientActivity.objects.for_photographer(profile).select_related(
            "client", "lead"
        ).order_by("-occurred_at")[:8],
    })
    return render(request, "photographer_workspace/clients_crm.html", context)


def _crm_form_page(request, form_class, title, success_message, activity_type=None):
    profile = request.user.photographer_profile
    model = form_class._meta.model
    kwargs = {"instance": model(photographer=profile)}
    if form_class is ClientTaskForm:
        kwargs["photographer"] = profile
    form = form_class(request.POST or None, **kwargs)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.photographer = profile
        record.full_clean()
        record.save()
        if isinstance(form, CrmClientForm) and form.cleaned_data.get("notes"):
            ClientNote.objects.create(photographer=profile, client=record, content=form.cleaned_data["notes"])
        if activity_type:
            ClientActivity.objects.create(photographer=profile, lead=record, event_type=activity_type, description=f"Lead {record} was created.")
        messages.success(request, success_message)
        return redirect("photographer_workspace:crm")
    context = _dashboard_context(request, "crm", title)
    context.update({
        "form": form,
        "form_title": title,
        "is_client_form": form_class is CrmClientForm,
        "is_lead_form": form_class is LeadForm,
    })
    return render(request, "photographer_workspace/crm_form.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def add_lead(request):
    return _crm_form_page(request, LeadForm, "Add Lead", "Lead added successfully.", ClientActivity.EventType.LEAD_CREATED)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def add_client(request):
    return _crm_form_page(request, CrmClientForm, "Add Client", "Client added successfully.")


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def create_task(request):
    return _crm_form_page(request, ClientTaskForm, "Create Task", "Task created successfully.")


@photographer_workspace_required
@require_POST
def complete_task(request, pk):
    task = get_object_or_404(ClientTask.objects.for_photographer(request.user.photographer_profile), pk=pk)
    task.status = ClientTask.Status.COMPLETED
    task.save(update_fields=["status", "updated_at"])
    messages.success(request, "Task marked complete.")
    return redirect("photographer_workspace:crm")


@photographer_workspace_required
@require_POST
def update_lead_status(request, pk):
    lead = get_object_or_404(Lead.objects.for_photographer(request.user.photographer_profile), pk=pk)
    status = request.POST.get("status")
    if status not in Lead.Status.values:
        messages.error(request, "Select a valid lead status.")
    elif Client.objects.filter(converted_lead=lead).exists():
        messages.error(request, "A converted lead must remain booked.")
    else:
        lead.status = status
        lead.save(update_fields=["status", "updated_at"])
        messages.success(request, "Lead status updated.")
    destination = "photographer_workspace:leads" if request.POST.get("next") == reverse("photographer_workspace:leads") else "photographer_workspace:crm"
    return redirect(destination)


@photographer_workspace_required
@require_GET
def leads_workspace(request):
    """Render the photographer-scoped lead pipeline in board or list form."""
    profile = request.user.photographer_profile
    leads = Lead.objects.for_photographer(profile).annotate(last_activity_at=Max("activities__occurred_at"))
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    source = request.GET.get("source", "").strip()
    if query:
        leads = leads.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(email__icontains=query) | Q(event_type__icontains=query)
        )
    if status in Lead.Status.values:
        leads = leads.filter(status=status)
    if source:
        leads = leads.filter(lead_source=source)

    allowed_sorts = {
        "newest": "-created_at", "oldest": "created_at", "name": "first_name",
        "event_date": F("event_date").asc(nulls_last=True),
        "value_high": F("estimated_value").desc(nulls_last=True),
        "value_low": F("estimated_value").asc(nulls_last=True),
    }
    sort = request.GET.get("sort", "newest")
    leads = leads.order_by(allowed_sorts.get(sort, "-created_at"))
    today = timezone.localdate()
    all_leads = Lead.objects.for_photographer(profile)
    booked = all_leads.filter(status=Lead.Status.BOOKED).count()
    total = all_leads.count()
    summary = [
        {"label": "New Leads", "value": all_leads.filter(status=Lead.Status.NEW).count(), "icon": "bi-person-plus", "note": "Awaiting first contact"},
        {"label": "Follow-ups Due", "value": all_leads.overdue_followups(today).count(), "icon": "bi-clock-history", "note": "Need your attention"},
        {"label": "Pipeline Value", "value": f"{profile.default_currency} {all_leads.pipeline_value():,.0f}", "icon": "bi-cash-stack", "note": "Open and booked leads"},
        {"label": "Conversion Rate", "value": f"{(booked / total * 100) if total else 0:.1f}%", "icon": "bi-graph-up-arrow", "note": "Leads moved to booked"},
    ]
    stages = [{"key": key, "label": "New Inquiry" if key == Lead.Status.NEW else label,
               "leads": list(leads.filter(status=key)), "count": leads.filter(status=key).count()}
              for key, label in Lead.Status.choices]
    paginator = Paginator(leads, 10)
    page = paginator.get_page(request.GET.get("page"))
    sources = Lead.objects.for_photographer(profile).exclude(lead_source="").values_list("lead_source", flat=True).distinct().order_by("lead_source")
    context = _dashboard_context(request, "leads", "Leads")
    context.update({"lead_summary": summary, "lead_stages": stages, "lead_page": page,
                    "lead_sources": sources, "lead_query": query, "selected_status": status,
                    "selected_source": source, "selected_sort": sort, "today": today,
                    "lead_status_choices": Lead.Status.choices})
    return render(request, "photographer_workspace/leads.html", context)


@photographer_workspace_required
@require_POST
def bulk_update_leads(request):
    leads = Lead.objects.for_photographer(request.user.photographer_profile).filter(pk__in=request.POST.getlist("lead_ids"))
    action = request.POST.get("action")
    if action in Lead.Status.values:
        updated = leads.update(status=action, updated_at=timezone.now())
        messages.success(request, f"Updated {updated} lead{'s' if updated != 1 else ''}.")
    else:
        messages.error(request, "Choose a valid bulk action.")
    return redirect("photographer_workspace:leads")


@photographer_workspace_required
@require_POST
def convert_lead(request, pk):
    profile = request.user.photographer_profile
    with transaction.atomic():
        lead = get_object_or_404(Lead.objects.select_for_update().for_photographer(profile), pk=pk)
        if Client.objects.filter(converted_lead=lead).exists():
            messages.error(request, "This lead has already been converted.")
            return redirect("photographer_workspace:crm")
        client, created = lead.convert_to_client()
        if not created:
            messages.error(request, "This lead has already been converted.")
            return redirect("photographer_workspace:crm")
        ClientActivity.objects.create(photographer=profile, lead=lead, client=client,
                                      event_type=ClientActivity.EventType.LEAD_CONVERTED,
                                      description=f"Lead {lead} converted to a client.")
    messages.success(request, "Lead converted to a client.")
    return redirect("photographer_workspace:crm")


@photographer_workspace_required
@require_GET
def module_placeholder(request, module_key):
    module = MODULE_BY_KEY[module_key]
    context = _dashboard_context(request, module_key, module["title"])
    context["module"] = module | {"url": _reverse_module(module)}
    return render(request, "photographer_workspace/placeholder.html", context)
