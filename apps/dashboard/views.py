from decimal import Decimal
import mimetypes

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from PIL import Image, UnidentifiedImageError

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead
from apps.clients.forms import ClientTaskForm, CrmClientForm, LeadForm
from apps.galleries.forms import GalleryForm
from apps.galleries.models import Gallery, GalleryPhoto
from apps.ai_engine.models import AIJob, AIProcessingStatus

WORKSPACE_MODULES = [
    {"key": "dashboard", "url_name": "dashboard", "icon": "bi-grid-1x2", "title": "Dashboard", "description": "Your business command center.", "coming_soon": False},
    {"key": "galleries", "url_name": "galleries", "icon": "bi-grid", "title": "Galleries Dashboard", "description": "Organize, publish, and deliver photography collections.", "coming_soon": False},
    {"key": "all_galleries", "url_name": "all_galleries", "icon": "bi-images", "title": "All Galleries", "description": "Browse every photography collection.", "coming_soon": False},
    {"key": "gallery_upload_queue", "url_name": "gallery_upload_queue", "icon": "bi-cloud-arrow-up", "title": "Upload Queue", "description": "Review gallery uploads and processing.", "coming_soon": False},
    {"key": "ai_processing", "url_name": "ai_processing", "icon": "bi-cpu", "title": "AI Processing", "description": "Monitor and manage gallery AI tasks.", "coming_soon": False},
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
    {"title": "Galleries", "icon": "bi-images", "items": [("galleries", "Galleries Dashboard", "bi-grid"), ("all_galleries", "All Galleries", "bi-images"), ("gallery_upload_queue", "Upload Queue", "bi-cloud-arrow-up"), ("ai_processing", "AI Processing", "bi-cpu"), ("ai_search", "AI Search", "bi-stars"), ("albums", "Albums", "bi-collection")]},
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
    outstanding = clients.outstanding_balances().aggregate(
        total=Coalesce(Sum("balance_due"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    sessions = clients.upcoming_sessions(now).select_related("client")
    metrics = [
        ("Total Leads", leads.count(), "bi-person-plus"),
        ("Active Clients", clients.active().count(), "bi-people"),
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
        "recent_activity": clients.recent_activity().select_related("client", "lead")[:8],
    })
    return render(request, "photographer_workspace/clients_crm.html", context)


def _crm_form_page(request, form_class, title, success_message, activity_type=None):
    profile = request.user.photographer_profile
    model = form_class._meta.model
    kwargs = {"instance": model(photographer=profile)}
    if form_class is ClientTaskForm:
        kwargs["photographer"] = profile
    form = form_class(request.POST or None, request.FILES or None, **kwargs)
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


def _lead_destination(request):
    """Only allow redirects back to known workspace pages."""
    return "photographer_workspace:crm" if request.POST.get("next") == reverse("photographer_workspace:crm") else "photographer_workspace:leads"


def _log_lead(profile, lead, event_type, description, metadata=None, client=None):
    return ClientActivity.objects.create(
        photographer=profile, lead=lead, client=client, event_type=event_type,
        description=description, metadata=metadata or {},
    )


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def add_lead(request):
    return _crm_form_page(request, LeadForm, "Add Lead", "Lead added successfully.", ClientActivity.EventType.LEAD_CREATED)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_lead(request, pk):
    profile = request.user.photographer_profile
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    form = LeadForm(request.POST or None, instance=lead)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.photographer = profile
        updated.full_clean()
        updated.save()
        _log_lead(profile, updated, ClientActivity.EventType.LEAD_UPDATED, f"Lead {updated} was updated.")
        messages.success(request, "Lead updated successfully.")
        return redirect("photographer_workspace:leads")
    context = _dashboard_context(request, "leads", "Edit Lead")
    context.update({"form": form, "form_title": "Edit Lead", "is_lead_form": True, "editing_lead": lead})
    return render(request, "photographer_workspace/crm_form.html", context)


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
        previous = lead.get_status_display()
        lead.status = status
        if status != Lead.Status.LOST:
            lead.lost_reason = ""
        lead.save(update_fields=["status", "lost_reason", "updated_at"])
        _log_lead(request.user.photographer_profile, lead, ClientActivity.EventType.STAGE_CHANGED,
                  f"Stage changed from {previous} to {lead.get_status_display()}.", {"from": previous, "to": status})
        messages.success(request, "Lead status updated.")
    destination = "photographer_workspace:leads" if request.POST.get("next") == reverse("photographer_workspace:leads") else "photographer_workspace:crm"
    return redirect(destination)


@photographer_workspace_required
@require_GET
def leads_workspace(request):
    """Render the photographer-scoped lead pipeline in board or list form."""
    profile = request.user.photographer_profile
    leads = Lead.objects.for_photographer(profile).filter(archived_at__isnull=True).prefetch_related("activities").annotate(last_activity_at=Max("activities__occurred_at"))
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    source = request.GET.get("source", "").strip()
    event_type = request.GET.get("event_type", "").strip()
    if query:
        leads = leads.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(email__icontains=query) | Q(event_type__icontains=query)
        )
    if status in Lead.Status.values:
        leads = leads.filter(status=status)
    if source:
        leads = leads.filter(lead_source=source)
    if event_type:
        leads = leads.filter(event_type=event_type)

    allowed_sorts = {
        "newest": "-created_at", "oldest": "created_at", "name": "first_name",
        "event_date": F("event_date").asc(nulls_last=True),
        "value_high": F("estimated_value").desc(nulls_last=True),
        "value_low": F("estimated_value").asc(nulls_last=True),
    }
    sort = request.GET.get("sort", "newest")
    leads = leads.order_by(allowed_sorts.get(sort, "-created_at"))
    today = timezone.localdate()
    all_leads = Lead.objects.for_photographer(profile).filter(archived_at__isnull=True)
    booked = all_leads.filter(status=Lead.Status.BOOKED).count()
    total = all_leads.count()
    summary = [
        {"label": "New Leads", "value": all_leads.filter(status=Lead.Status.NEW).count(), "icon": "bi-person-plus", "note": "Awaiting first contact"},
        {"label": "Follow-ups Due", "value": all_leads.overdue_followups(today).count(), "icon": "bi-clock-history", "note": "Need your attention"},
        {"label": "Pipeline Value", "value": f"{profile.default_currency} {all_leads.pipeline_value():,.0f}", "icon": "bi-cash-stack", "note": "Open and booked leads"},
        {"label": "Conversion Rate", "value": f"{(booked / total * 100) if total else 0:.1f}%", "icon": "bi-graph-up-arrow", "note": "Leads moved to booked"},
    ]
    stages = [{"key": key, "label": "New Inquiry" if key == Lead.Status.NEW else label,
               "leads": list(leads.filter(status=key)), "count": leads.filter(status=key).count(),
               "value": leads.filter(status=key).aggregate(total=Coalesce(Sum("estimated_value"), Value(Decimal("0")), output_field=DecimalField()))["total"]}
              for key, label in Lead.Status.choices]
    paginator = Paginator(leads, 10)
    page = paginator.get_page(request.GET.get("page"))
    sources = Lead.objects.for_photographer(profile).exclude(lead_source="").values_list("lead_source", flat=True).distinct().order_by("lead_source")
    event_types = Lead.objects.for_photographer(profile).exclude(event_type="").values_list("event_type", flat=True).distinct().order_by("event_type")
    tasks_due = ClientTask.objects.filter(photographer=profile, lead__isnull=False, status__in=[ClientTask.Status.OPEN, ClientTask.Status.IN_PROGRESS]).select_related("lead").order_by(F("due_date").asc(nulls_last=True))[:5]
    recent_activity = ClientActivity.objects.filter(photographer=profile, lead__isnull=False).select_related("lead").order_by("-occurred_at")[:5]
    source_rows = list(all_leads.exclude(lead_source="").values("lead_source").annotate(count=Count("id")).order_by("-count")[:5])
    source_total = sum(row["count"] for row in source_rows)
    for row in source_rows:
        row["percent"] = round(row["count"] / source_total * 100) if source_total else 0
    context = _dashboard_context(request, "leads", "Leads")
    context.update({"lead_summary": summary, "lead_stages": stages, "lead_page": page,
                    "lead_sources": sources, "lead_query": query, "selected_status": status,
                    "selected_source": source, "selected_event_type": event_type, "event_types": event_types,
                    "selected_sort": sort, "today": today, "tasks_due": tasks_due,
                    "recent_activity": recent_activity, "source_rows": source_rows,
                    "lead_status_choices": Lead.Status.choices})
    return render(request, "photographer_workspace/leads.html", context)


@photographer_workspace_required
@require_GET
def clients_workspace(request):
    """Render the searchable, photographer-scoped client directory."""
    profile = request.user.photographer_profile
    now = timezone.now()
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=DecimalField(max_digits=12, decimal_places=2))
    upcoming = ClientSession.objects.filter(
        photographer=profile, client=OuterRef("pk"), starts_at__gte=now,
    ).exclude(status=ClientSession.Status.CANCELLED).order_by("starts_at")
    invoices = ClientInvoice.objects.filter(
        photographer=profile, client=OuterRef("pk"),
    ).exclude(status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID]).values("client").annotate(
        due=Sum(balance)
    )
    activity = ClientActivity.objects.filter(
        photographer=profile, client=OuterRef("pk")
    ).order_by("-occurred_at")
    clients = Client.objects.for_photographer(profile).annotate(
        next_session_at=Subquery(upcoming.values("starts_at")[:1]),
        next_session_type=Subquery(upcoming.values("session_type")[:1]),
        outstanding_balance=Coalesce(Subquery(invoices.values("due")[:1]), Value(Decimal("0.00")), output_field=DecimalField()),
        last_activity_at=Subquery(activity.values("occurred_at")[:1]),
        last_activity_label=Subquery(activity.values("description")[:1]),
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    client_type = request.GET.get("client_type", "").strip()
    tag = request.GET.get("tag", "").strip()
    has_session = request.GET.get("upcoming", "").strip()
    has_balance = request.GET.get("balance", "").strip()
    if query:
        clients = clients.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) |
                                 Q(email__icontains=query) | Q(phone__icontains=query) | Q(company__icontains=query))
    if status in Client.Status.values:
        clients = clients.filter(status=status)
    if client_type in Client.ClientType.values:
        clients = clients.filter(client_type=client_type)
    if tag:
        matching_ids = [client.pk for client in clients.only("pk", "tags") if tag.casefold() in {str(item).casefold() for item in client.tags}]
        clients = clients.filter(pk__in=matching_ids)
    if has_session == "yes":
        clients = clients.filter(next_session_at__isnull=False)
    elif has_session == "no":
        clients = clients.filter(next_session_at__isnull=True)
    if has_balance == "yes":
        clients = clients.filter(outstanding_balance__gt=0)
    elif has_balance == "no":
        clients = clients.filter(outstanding_balance=0)
    clients = clients.order_by("last_name", "first_name")

    all_clients = Client.objects.for_photographer(profile)
    outstanding_total = all_clients.outstanding_balances().aggregate(
        total=Coalesce(Sum("balance_due"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    summary = [
        {"label": "Total Clients", "value": all_clients.count(), "icon": "bi-people", "note": "All client relationships"},
        {"label": "Active Clients", "value": all_clients.active().count(), "icon": "bi-person-check", "note": "Currently active"},
        {"label": "Upcoming Sessions", "value": all_clients.upcoming_sessions(now).count(), "icon": "bi-calendar2-check", "note": "Scheduled from today"},
        {"label": "Outstanding Balance", "value": f"{profile.default_currency} {outstanding_total:,.2f}", "icon": "bi-wallet2", "note": "Across open invoices"},
    ]
    tags = sorted({str(tag) for values in all_clients.values_list("tags", flat=True) for tag in (values or [])}, key=str.casefold)
    paginator = Paginator(clients, 12)
    page = paginator.get_page(request.GET.get("page"))
    retained = request.GET.copy()
    retained.pop("page", None)
    context = _dashboard_context(request, "clients", "Clients")
    context.update({
        "client_summary": summary, "client_page": page, "client_query": query,
        "selected_status": status, "selected_client_type": client_type, "selected_tag": tag,
        "selected_upcoming": has_session, "selected_balance": has_balance, "client_tags": tags,
        "client_status_choices": Client.Status.choices, "client_type_choices": Client.ClientType.choices,
        "retained_query": retained.urlencode(),
    })
    return render(request, "photographer_workspace/clients.html", context)


GALLERY_STORAGE_LIMIT = 100 * 1024**3


def _format_storage(byte_count):
    """Return a compact, presentation-ready storage value."""
    if byte_count >= 1024**3:
        return f"{byte_count / 1024**3:.1f} GB"
    if byte_count >= 1024**2:
        return f"{byte_count / 1024**2:.1f} MB"
    return f"{byte_count / 1024:.1f} KB" if byte_count else "0 GB"


def _gallery_summary(galleries, storage_used):
    return [
        {"label": "Total Galleries", "value": galleries.count(), "icon": "bi-images", "note": "All collections"},
        {"label": "Active Galleries", "value": galleries.exclude(status__in=[Gallery.Status.ARCHIVED, Gallery.Status.EXPIRED, Gallery.Status.DELIVERED]).count(), "icon": "bi-activity", "note": "Currently in your workflow"},
        {"label": "Ready to Deliver", "value": galleries.filter(status=Gallery.Status.READY).count(), "icon": "bi-send-check", "note": "Awaiting delivery"},
        {"label": "Storage Used", "value": _format_storage(storage_used), "icon": "bi-device-ssd", "note": f"{round(storage_used / GALLERY_STORAGE_LIMIT * 100)}% of 100 GB"},
    ]


@photographer_workspace_required
@require_GET
def galleries_dashboard(request):
    galleries = Gallery.objects.for_photographer(request.user.photographer_profile).select_related("client")
    now = timezone.now()
    storage_used = galleries.aggregate(total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField()))["total"]
    pipeline_counts = {row["status"]: row["count"] for row in galleries.values("status").annotate(count=Count("id"))}
    pipeline = [
        {"key": key, "label": label, "count": pipeline_counts.get(key, 0), "percent": round(pipeline_counts.get(key, 0) / max(galleries.count(), 1) * 100)}
        for key, label in Gallery.Status.choices
        if key not in {Gallery.Status.ARCHIVED, Gallery.Status.EXPIRED}
    ]
    activity = []
    for gallery in galleries.filter(client__isnull=False)[:8]:
        if gallery.download_count:
            activity.append({"icon": "bi-download", "action": "Gallery downloaded", "client": str(gallery.client), "gallery": gallery.name, "time": gallery.updated_at})
        if gallery.favorite_count:
            activity.append({"icon": "bi-heart", "action": "Photo favorited", "client": str(gallery.client), "gallery": gallery.name, "time": gallery.updated_at})
        if gallery.status in {Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED}:
            activity.append({"icon": "bi-eye", "action": "Client viewed gallery", "client": str(gallery.client), "gallery": gallery.name, "time": gallery.published_at or gallery.updated_at})
    deadlines = []
    for gallery in galleries.filter(Q(expires_at__gte=now) | Q(event_date__gte=timezone.localdate())).order_by("expires_at", "event_date")[:6]:
        if gallery.expires_at:
            days = (gallery.expires_at.date() - timezone.localdate()).days
            deadlines.append({"gallery": gallery, "type": "Expires", "date": gallery.expires_at, "urgency": "Urgent" if days <= 3 else "Soon", "urgent": days <= 3})
        elif gallery.event_date:
            days = (gallery.event_date - timezone.localdate()).days
            deadlines.append({"gallery": gallery, "type": "Delivery target", "date": gallery.event_date, "urgency": "Urgent" if days <= 3 else "Upcoming", "urgent": days <= 3})
    context = _dashboard_context(request, "galleries", "Galleries")
    context.update({
        "gallery_summary": _gallery_summary(galleries, storage_used), "recent_galleries": galleries[:6],
        "delivery_pipeline": pipeline, "recent_client_activity": sorted(activity, key=lambda item: item["time"], reverse=True)[:6],
        "storage": {"used": _format_storage(storage_used), "available": _format_storage(max(GALLERY_STORAGE_LIMIT - storage_used, 0)), "percent": min(round(storage_used / GALLERY_STORAGE_LIMIT * 100), 100)},
        "gallery_deadlines": deadlines,
    })
    return render(request, "photographer_workspace/galleries/dashboard.html", context)


def _unique_gallery_slug(profile, name, exclude_pk=None):
    base = slugify(name)[:200] or "gallery"
    slug, suffix = base, 2
    matches = Gallery.objects.for_photographer(profile)
    if exclude_pk:
        matches = matches.exclude(pk=exclude_pk)
    while matches.filter(slug=slug).exists():
        slug = f"{base[:210-len(str(suffix))]}-{suffix}"
        suffix += 1
    return slug


AI_TASK_ICONS = {
    AIJob.TaskType.FACE_DETECTION: "bi-person-bounding-box", AIJob.TaskType.FACE_CLUSTERING: "bi-people",
    AIJob.TaskType.DUPLICATE_DETECTION: "bi-copy", AIJob.TaskType.BLUR_DETECTION: "bi-droplet-half",
    AIJob.TaskType.CLOSED_EYES_DETECTION: "bi-eye-slash", AIJob.TaskType.IMAGE_QUALITY_SCORING: "bi-stars",
    AIJob.TaskType.SCENE_RECOGNITION: "bi-image", AIJob.TaskType.OBJECT_DETECTION: "bi-bounding-box-circles",
    AIJob.TaskType.COLOR_DETECTION: "bi-palette", AIJob.TaskType.KEYWORD_GENERATION: "bi-tags",
    AIJob.TaskType.SEARCH_INDEXING: "bi-search",
}


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def ai_processing_center(request):
    profile = request.user.photographer_profile
    galleries = Gallery.objects.for_photographer(profile).order_by("name")
    if request.method == "POST":
        gallery_ids = request.POST.getlist("gallery_ids")
        task_types = request.POST.getlist("task_types")
        selected_galleries = galleries.filter(pk__in=gallery_ids)
        valid_tasks = [task for task in task_types if task in AIJob.TaskType.values]
        created = 0
        with transaction.atomic():
            for gallery in selected_galleries:
                for task_type in valid_tasks:
                    if AIJob.objects.filter(gallery=gallery, task_type=task_type, status__in=[AIJob.Status.QUEUED, AIJob.Status.RUNNING]).exists():
                        continue
                    job = AIJob.objects.create(photographer=profile, gallery=gallery, task_type=task_type, estimated_seconds=max(gallery.image_count * 2, 60))
                    AIProcessingStatus.objects.create(job=job, total_images=gallery.image_count)
                    created += 1
        if created:
            messages.success(request, f"{created} AI processing job{'s' if created != 1 else ''} added to the queue.")
        else:
            messages.warning(request, "Select at least one gallery and AI task, or choose work that is not already active.")
        return redirect("photographer_workspace:ai_processing")

    jobs = AIJob.objects.for_photographer(profile).select_related("gallery", "gallery__client", "progress")
    active_jobs = list(jobs.active().order_by("queued_at"))
    completed_jobs = list(jobs.filter(status=AIJob.Status.COMPLETED)[:10])
    failed_jobs = list(jobs.filter(status=AIJob.Status.FAILED)[:8])
    capabilities = []
    for task_type, label in AIJob.TaskType.choices:
        latest = jobs.filter(task_type=task_type).first()
        capabilities.append({"key": task_type, "label": label, "icon": AI_TASK_ICONS[task_type], "job": latest})
    context = _dashboard_context(request, "ai_processing", "AI Processing")
    context.update({
        "galleries": galleries, "task_choices": AIJob.TaskType.choices, "queue_jobs": active_jobs,
        "completed_jobs": completed_jobs, "failed_jobs": failed_jobs, "capabilities": capabilities,
        "ai_summary": [
            {"label": "Galleries Processing", "value": jobs.filter(status=AIJob.Status.RUNNING).values("gallery").distinct().count(), "icon": "bi-images", "tone": "purple"},
            {"label": "Images Processed", "value": sum(getattr(job, "progress", None).completed_images for job in jobs.filter(status=AIJob.Status.COMPLETED) if getattr(job, "progress", None)), "icon": "bi-check2-circle", "tone": "green"},
            {"label": "Pending Jobs", "value": jobs.filter(status=AIJob.Status.QUEUED).count(), "icon": "bi-clock", "tone": "amber"},
            {"label": "Failed Jobs", "value": jobs.filter(status=AIJob.Status.FAILED).count(), "icon": "bi-exclamation-triangle", "tone": "red"},
        ],
    })
    return render(request, "photographer_workspace/galleries/ai_processing.html", context)


@photographer_workspace_required
@require_POST
def ai_job_action(request, pk):
    job = get_object_or_404(AIJob.objects.for_photographer(request.user.photographer_profile), pk=pk)
    action = request.POST.get("action")
    if action == "retry" and job.status == AIJob.Status.FAILED:
        job.status, job.error_summary, job.error_details = AIJob.Status.QUEUED, "", ""
        job.started_at, job.completed_at = None, None
        job.save(update_fields=["status", "error_summary", "error_details", "started_at", "completed_at", "updated_at"])
        AIProcessingStatus.objects.update_or_create(job=job, defaults={"total_images": job.gallery.image_count, "completed_images": 0, "failed_images": 0, "current_stage": ""})
        messages.success(request, "The AI job was returned to the queue.")
    elif action == "cancel" and job.status in {AIJob.Status.QUEUED, AIJob.Status.RUNNING, AIJob.Status.FAILED}:
        job.status, job.completed_at = AIJob.Status.CANCELLED, timezone.now()
        job.save(update_fields=["status", "completed_at", "updated_at"])
        messages.success(request, "The AI job was cancelled.")
    return redirect("photographer_workspace:ai_processing")


@photographer_workspace_required
@require_GET
def all_galleries(request):
    profile = request.user.photographer_profile
    all_records = Gallery.objects.for_photographer(profile).select_related("client")
    galleries = all_records
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    client = request.GET.get("client", "").strip()
    event_date = request.GET.get("event_date", "").strip()
    sort = request.GET.get("sort", "updated").strip()
    if query:
        galleries = galleries.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(client__first_name__icontains=query) | Q(client__last_name__icontains=query))
    if status in Gallery.Status.values:
        galleries = galleries.filter(status=status)
    if client.isdigit():
        galleries = galleries.filter(client_id=client)
    if event_date:
        galleries = galleries.filter(event_date=event_date)
    ordering = {"updated": "-updated_at", "newest": "-created_at", "name": "name", "event_soon": "event_date", "images": "-image_count"}
    galleries = galleries.order_by(ordering.get(sort, "-updated_at"))
    paginator = Paginator(galleries, 12)
    page = paginator.get_page(request.GET.get("page"))
    retained = request.GET.copy()
    retained.pop("page", None)
    summary = [
        {"label": "All Galleries", "value": all_records.count(), "status": ""},
        {"label": "Draft", "value": all_records.filter(status=Gallery.Status.DRAFT).count(), "status": Gallery.Status.DRAFT},
        {"label": "Processing", "value": all_records.filter(status__in=[Gallery.Status.UPLOADING, Gallery.Status.PROCESSING]).count(), "status": Gallery.Status.PROCESSING},
        {"label": "Ready", "value": all_records.filter(status=Gallery.Status.READY).count(), "status": Gallery.Status.READY},
        {"label": "Published", "value": all_records.filter(status=Gallery.Status.PUBLISHED).count(), "status": Gallery.Status.PUBLISHED},
    ]
    context = _dashboard_context(request, "all_galleries", "All Galleries")
    context.update({"gallery_page": page, "gallery_query": query, "selected_status": status,
        "selected_client": client, "selected_event_date": event_date, "selected_sort": sort,
        "gallery_status_choices": Gallery.Status.choices, "gallery_clients": Client.objects.for_photographer(profile).order_by("first_name", "last_name"),
        "gallery_summary_strip": summary, "retained_query": retained.urlencode(), "has_filters": any([query, status, client, event_date])})
    return render(request, "photographer_workspace/galleries/all.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def create_gallery(request):
    profile = request.user.photographer_profile
    form = GalleryForm(request.POST or None, request.FILES or None, photographer=profile)
    if request.method == "POST" and form.is_valid():
        gallery = form.save(commit=False)
        gallery.photographer = profile
        gallery.slug = _unique_gallery_slug(profile, gallery.name)
        gallery.full_clean()
        gallery.save()
        messages.success(request, "Gallery created. Your workspace is ready.")
        return redirect("photographer_workspace:gallery_workspace", pk=gallery.pk)
    context = _dashboard_context(request, "all_galleries", "Create Gallery")
    context.update({"form": form, "form_title": "Create Gallery", "form_subtitle": "Set up the essentials now—you can add photos and delivery settings next.", "submit_label": "Create Gallery"})
    return render(request, "photographer_workspace/galleries/form.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_gallery(request, pk):
    profile = request.user.photographer_profile
    gallery = get_object_or_404(Gallery.objects.for_photographer(profile), pk=pk)
    form = GalleryForm(request.POST or None, request.FILES or None, instance=gallery, photographer=profile)
    if request.method == "POST" and form.is_valid():
        gallery = form.save(commit=False)
        gallery.slug = _unique_gallery_slug(profile, gallery.name, gallery.pk)
        gallery.full_clean()
        gallery.save()
        messages.success(request, "Gallery updated.")
        return redirect("photographer_workspace:all_galleries")
    context = _dashboard_context(request, "all_galleries", "Edit Gallery")
    context.update({"form": form, "gallery": gallery, "form_title": "Edit Gallery", "form_subtitle": "Update gallery details, access, and availability.", "submit_label": "Save Changes"})
    return render(request, "photographer_workspace/galleries/form.html", context)


@photographer_workspace_required
@require_POST
def gallery_actions(request):
    profile = request.user.photographer_profile
    ids = request.POST.getlist("gallery_ids")
    records = Gallery.objects.for_photographer(profile).filter(pk__in=ids)
    action = request.POST.get("action")
    if not ids:
        messages.error(request, "Select at least one gallery.")
    elif action == "delete":
        count = records.count()
        records.delete()
        messages.success(request, f"Deleted {count} {'gallery' if count == 1 else 'galleries'}.")
    elif action == "archive":
        records.update(status=Gallery.Status.ARCHIVED)
        messages.success(request, "Selected galleries archived.")
    elif action == "publish":
        records.update(status=Gallery.Status.PUBLISHED, published_at=timezone.now())
        messages.success(request, "Selected galleries published.")
    elif action == "status" and request.POST.get("status") in Gallery.Status.values:
        records.update(status=request.POST["status"])
        messages.success(request, "Gallery status updated.")
    elif action == "duplicate" and len(ids) == 1:
        original = records.first()
        original.pk = None
        original.name = f"{original.name} Copy"
        original.slug = _unique_gallery_slug(profile, original.name)
        original.status = Gallery.Status.DRAFT
        original.published_at = None
        original.save()
        messages.success(request, "Gallery duplicated as a draft.")
    else:
        messages.error(request, "Choose a valid gallery action.")
    return redirect("photographer_workspace:all_galleries")


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def gallery_upload_queue(request):
    profile = request.user.photographer_profile
    galleries = Gallery.objects.for_photographer(profile).select_related("client")
    if request.method == "POST":
        gallery = get_object_or_404(galleries, pk=request.POST.get("gallery"))
        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"error": "Choose at least one image."}, status=400)
        created, errors = [], []
        allowed = {"image/jpeg", "image/png", "image/webp"}
        max_size = 25 * 1024 * 1024
        for upload in files:
            if upload.content_type not in allowed or upload.size > max_size:
                errors.append({"name": upload.name, "error": "Use a JPG, PNG, or WebP image up to 25 MB."})
                continue
            try:
                image = Image.open(upload)
                image.verify()
                upload.seek(0)
            except (UnidentifiedImageError, OSError):
                errors.append({"name": upload.name, "error": "The file is not a valid image."})
                continue
            photo = GalleryPhoto(gallery=gallery, photographer=profile, file=upload, original_name=upload.name[:255], file_size=upload.size, status=GalleryPhoto.Status.COMPLETED)
            try:
                photo.full_clean()
                photo.save()
            except Exception:
                errors.append({"name": upload.name, "error": "The image could not be validated."})
                continue
            created.append({"id": photo.pk, "name": photo.original_name, "size": photo.file_size, "status": photo.status})
        if created:
            Gallery.objects.filter(pk=gallery.pk).update(image_count=F("image_count") + len(created), storage_used=F("storage_used") + sum(item["size"] for item in created))
        return JsonResponse({"uploads": created, "errors": errors}, status=201 if created else 400)
    upload_records = GalleryPhoto.objects.for_photographer(profile)
    counts = {status: upload_records.filter(status=status).count() for status in GalleryPhoto.Status.values}
    uploads = upload_records.select_related("gallery")[:100]
    storage_used = galleries.aggregate(total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField()))["total"]
    context = _dashboard_context(request, "gallery_upload_queue", "Upload Queue")
    context.update({"gallery_choices": galleries, "uploads": uploads, "upload_counts": counts,
                    "storage": {"used": _format_storage(storage_used), "percent": min(round(storage_used / GALLERY_STORAGE_LIMIT * 100), 100)}})
    return render(request, "photographer_workspace/galleries/upload_queue.html", context)


@photographer_workspace_required
@require_GET
def gallery_workspace(request, pk):
    gallery = get_object_or_404(
        Gallery.objects.for_photographer(request.user.photographer_profile).select_related("client"), pk=pk
    )
    context = _dashboard_context(request, "all_galleries", gallery.name)
    tab = request.GET.get("tab", "overview")
    tabs = ("overview", "photos", "albums", "ai-tools", "client-access", "store", "downloads", "activity", "settings")
    if tab not in tabs:
        tab = "overview"
    photos = gallery.photos.all()
    query = request.GET.get("q", "").strip()
    if query:
        photos = photos.filter(original_name__icontains=query)
    photos = photos.order_by("original_name" if request.GET.get("sort") == "name" else "-created_at")
    context.update({"gallery": gallery, "active_tab": tab, "photos": photos, "storage_display": _format_storage(gallery.storage_used),
                    "upload_percent": 100 if gallery.image_count else 0})
    return render(request, "photographer_workspace/galleries/workspace.html", context)


@photographer_workspace_required
@require_GET
def gallery_photo_media(request, pk):
    photo = get_object_or_404(GalleryPhoto.objects.for_photographer(request.user.photographer_profile), pk=pk)
    content_type = mimetypes.guess_type(photo.original_name)[0] or "application/octet-stream"
    response = FileResponse(photo.file.open("rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{photo.original_name.replace(chr(34), "")}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@photographer_workspace_required
@require_POST
def gallery_photo_action(request, pk):
    photo = get_object_or_404(GalleryPhoto.objects.for_photographer(request.user.photographer_profile).select_related("gallery"), pk=pk)
    action = request.POST.get("action")
    if action == "delete":
        Gallery.objects.filter(pk=photo.gallery_id).update(image_count=F("image_count") - 1, storage_used=F("storage_used") - photo.file_size)
        photo.file.delete(save=False)
        photo.delete()
    elif action == "cover":
        GalleryPhoto.objects.filter(gallery=photo.gallery).update(is_cover=False)
        photo.is_cover = True
        photo.save(update_fields=["is_cover", "updated_at"])
    elif action == "remove":
        # Queue dismissal is a presentation concern; it must never delete the gallery original.
        pass
    elif action == "retry" and photo.status == GalleryPhoto.Status.FAILED:
        photo.status, photo.error_message = GalleryPhoto.Status.QUEUED, ""
        photo.save(update_fields=["status", "error_message", "updated_at"])
    else:
        return JsonResponse({"error": "Unsupported action."}, status=400)
    return JsonResponse({"ok": True})


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_client(request, pk):
    profile = request.user.photographer_profile
    client = get_object_or_404(Client.objects.for_photographer(profile), pk=pk)
    form = CrmClientForm(request.POST or None, request.FILES or None, instance=client)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.photographer = profile
        client.full_clean()
        client.save()
        ClientActivity.objects.create(photographer=profile, client=client, event_type=ClientActivity.EventType.CLIENT_UPDATED, description=f"Client {client} was updated.")
        messages.success(request, "Client updated.")
        return redirect("photographer_workspace:client_detail", pk=client.pk)
    context = _dashboard_context(request, "clients", "Edit Client")
    context.update({"form": form, "form_title": "Edit Client", "is_client_form": True})
    return render(request, "photographer_workspace/crm_form.html", context)


CLIENT_DETAIL_TABS = ("overview", "projects", "sessions", "galleries", "contracts", "invoices", "questionnaires", "files", "activity")


@photographer_workspace_required
@require_GET
def client_detail(request, pk):
    profile = request.user.photographer_profile
    client = get_object_or_404(Client.objects.for_photographer(profile), pk=pk)
    now, today = timezone.now(), timezone.localdate()
    sessions = ClientSession.objects.for_photographer(profile).filter(client=client)
    invoices = ClientInvoice.objects.for_photographer(profile).filter(client=client)
    open_invoices = invoices.exclude(status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID])
    outstanding = sum((invoice.balance for invoice in open_invoices), Decimal("0.00"))
    upcoming = sessions.filter(starts_at__gte=now).exclude(status=ClientSession.Status.CANCELLED).first()
    overdue = open_invoices.filter(due_date__lt=today)
    soon = sessions.filter(starts_at__gte=now, starts_at__lte=now + timezone.timedelta(days=7)).exclude(status=ClientSession.Status.CANCELLED)
    tab = request.GET.get("tab", "overview")
    if tab not in CLIENT_DETAIL_TABS:
        tab = "overview"
    activities = ClientActivity.objects.for_photographer(profile).filter(client=client)
    context = _dashboard_context(request, "clients", str(client))
    context.update({
        "client_record": client, "detail_tabs": CLIENT_DETAIL_TABS, "active_tab": tab,
        "sessions": sessions, "invoices": invoices, "upcoming_session": upcoming,
        "outstanding_balance": outstanding, "recent_notes": client.notes.all()[:5],
        "client_tasks": client.tasks.exclude(status__in=[ClientTask.Status.COMPLETED, ClientTask.Status.CANCELLED]),
        "activities": activities[:30],
        "operational_alerts": [
            {"label": "Overdue invoices", "count": overdue.count(), "icon": "bi-receipt", "urgent": overdue.exists()},
            {"label": "Unsigned contracts", "count": 0, "icon": "bi-file-earmark-signature", "urgent": False},
            {"label": "Sessions in 7 days", "count": soon.count(), "icon": "bi-calendar-event", "urgent": soon.exists()},
            {"label": "Galleries awaiting delivery", "count": 0, "icon": "bi-images", "urgent": False},
        ],
    })
    return render(request, "photographer_workspace/client_detail.html", context)


@photographer_workspace_required
@require_POST
def client_archive_restore(request, pk):
    profile = request.user.photographer_profile
    client = get_object_or_404(Client.objects.for_photographer(profile), pk=pk)
    restoring = client.status == Client.Status.ARCHIVED
    client.status = Client.Status.ACTIVE if restoring else Client.Status.ARCHIVED
    client.save(update_fields=["status", "updated_at"])
    event = ClientActivity.EventType.CLIENT_RESTORED if restoring else ClientActivity.EventType.CLIENT_ARCHIVED
    verb = "restored" if restoring else "archived"
    ClientActivity.objects.create(photographer=profile, client=client, event_type=event, description=f"Client {client} was {verb}.")
    messages.success(request, f"Client {verb}.")
    return redirect("photographer_workspace:client_detail", pk=client.pk)


@photographer_workspace_required
@require_POST
def add_client_note(request, pk):
    profile = request.user.photographer_profile
    client = get_object_or_404(Client.objects.for_photographer(profile), pk=pk)
    content = request.POST.get("content", "").strip()
    if not content:
        messages.error(request, "Enter a note before saving.")
    elif len(content) > 5000:
        messages.error(request, "Notes must be 5,000 characters or fewer.")
    else:
        ClientNote.objects.create(photographer=profile, client=client, content=content)
        ClientActivity.objects.create(photographer=profile, client=client, event_type=ClientActivity.EventType.NOTE_ADDED, description="A client note was added.")
        messages.success(request, "Note added.")
    return redirect("photographer_workspace:client_detail", pk=client.pk)


@photographer_workspace_required
@require_POST
def add_client_task(request, pk):
    profile = request.user.photographer_profile
    client = get_object_or_404(Client.objects.for_photographer(profile), pk=pk)
    data = request.POST.copy()
    data["client"] = client.pk
    data.pop("lead", None)
    form = ClientTaskForm(data, photographer=profile, instance=ClientTask(photographer=profile))
    if form.is_valid():
        task = form.save(commit=False)
        task.photographer = profile
        task.full_clean()
        task.save()
        ClientActivity.objects.create(photographer=profile, client=client, event_type=ClientActivity.EventType.FOLLOW_UP_CREATED, description=f"Task created: {task.title}.")
        messages.success(request, "Task created.")
    else:
        messages.error(request, "Enter valid task details.")
    return redirect("photographer_workspace:client_detail", pk=client.pk)


@photographer_workspace_required
@require_POST
def bulk_update_leads(request):
    profile = request.user.photographer_profile
    leads = Lead.objects.for_photographer(profile).filter(pk__in=request.POST.getlist("lead_ids"), archived_at__isnull=True)
    action = request.POST.get("action")
    if action == Lead.Status.LOST:
        messages.error(request, "Mark leads lost individually so a reason can be recorded.")
    elif action in Lead.Status.values:
        updated = 0
        with transaction.atomic():
            for lead in leads.select_for_update():
                if hasattr(lead, "converted_client") and action != Lead.Status.BOOKED:
                    continue
                previous = lead.get_status_display()
                lead.status = action
                lead.save(update_fields=["status", "updated_at"])
                _log_lead(profile, lead, ClientActivity.EventType.STAGE_CHANGED,
                          f"Stage changed from {previous} to {lead.get_status_display()}.", {"from": previous, "to": action})
                updated += 1
        messages.success(request, f"Updated {updated} lead{'s' if updated != 1 else ''}.")
    else:
        messages.error(request, "Choose a valid bulk action.")
    return redirect("photographer_workspace:leads")


@photographer_workspace_required
@require_POST
def archive_lead(request, pk):
    profile = request.user.photographer_profile
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    lead.archived_at = timezone.now()
    lead.save(update_fields=["archived_at", "updated_at"])
    _log_lead(profile, lead, ClientActivity.EventType.LEAD_ARCHIVED, f"Lead {lead} was archived.")
    messages.success(request, "Lead archived.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def create_lead_follow_up(request, pk):
    profile = request.user.photographer_profile
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    title = request.POST.get("title", "").strip()
    due_date = request.POST.get("due_date", "").strip()
    if not title or not due_date:
        messages.error(request, "Enter a follow-up title and due date.")
    else:
        form = ClientTaskForm(
            {"title": title, "due_date": due_date, "priority": request.POST.get("priority", "medium"), "lead": lead.pk},
            photographer=profile, instance=ClientTask(photographer=profile),
        )
        if form.is_valid():
            task = form.save(commit=False)
            task.photographer = profile
            task.full_clean()
            task.save()
            lead.next_follow_up = task.due_date
            lead.save(update_fields=["next_follow_up", "updated_at"])
            _log_lead(profile, lead, ClientActivity.EventType.FOLLOW_UP_CREATED, f"Follow-up task created: {task.title}.", {"task_id": task.pk})
            messages.success(request, "Follow-up task created.")
        else:
            messages.error(request, "Check the follow-up details and try again.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def mark_lead_booked(request, pk):
    profile = request.user.photographer_profile
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    lead.status, lead.lost_reason = Lead.Status.BOOKED, ""
    lead.save(update_fields=["status", "lost_reason", "updated_at"])
    _log_lead(profile, lead, ClientActivity.EventType.LEAD_BOOKED, f"Lead {lead} was marked booked.")
    messages.success(request, "Lead marked booked.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def mark_lead_lost(request, pk):
    profile = request.user.photographer_profile
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Provide a reason before marking this lead lost.")
    elif len(reason) > 255:
        messages.error(request, "Lost reason must be 255 characters or fewer.")
    else:
        lead.status, lead.lost_reason = Lead.Status.LOST, reason
        lead.save(update_fields=["status", "lost_reason", "updated_at"])
        _log_lead(profile, lead, ClientActivity.EventType.LEAD_LOST, f"Lead marked lost: {reason}", {"reason": reason})
        messages.success(request, "Lead marked lost.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def add_lead_note(request, pk):
    profile = request.user.photographer_profile
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    note = request.POST.get("note", "").strip()
    if not note:
        messages.error(request, "Enter a note before saving.")
    elif len(note) > 2000:
        messages.error(request, "Notes must be 2,000 characters or fewer.")
    else:
        lead.notes = f"{lead.notes}\n\n{note}".strip()
        lead.save(update_fields=["notes", "updated_at"])
        _log_lead(profile, lead, ClientActivity.EventType.NOTE_ADDED, note)
        messages.success(request, "Note added.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def convert_lead(request, pk):
    profile = request.user.photographer_profile
    with transaction.atomic():
        lead = get_object_or_404(Lead.objects.select_for_update().for_photographer(profile), pk=pk)
        if Client.objects.filter(converted_lead=lead).exists():
            messages.error(request, "This lead has already been converted.")
            return redirect(_lead_destination(request))
        client, created = lead.convert_to_client()
        if not created:
            messages.error(request, "This lead has already been converted.")
            return redirect(_lead_destination(request))
        ClientActivity.objects.create(photographer=profile, lead=lead, client=client,
                                      event_type=ClientActivity.EventType.LEAD_CONVERTED,
                                      description=f"Lead {lead} converted to a client.")
    messages.success(request, "Lead converted to a client.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_GET
def module_placeholder(request, module_key):
    module = MODULE_BY_KEY[module_key]
    context = _dashboard_context(request, module_key, module["title"])
    context["module"] = module | {"url": _reverse_module(module)}
    return render(request, "photographer_workspace/placeholder.html", context)
