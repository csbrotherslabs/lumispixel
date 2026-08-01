from decimal import Decimal
from calendar import Calendar
from datetime import date, datetime, time, timedelta
import csv
import io
import mimetypes
import zipfile
import secrets
from urllib.parse import urlencode

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, HttpResponse, JsonResponse
from django.db import transaction
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from PIL import Image, UnidentifiedImageError

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, InvoiceActivity, InvoiceCredit, InvoiceLineItem, InvoicePayment, Lead, PaymentRefund
from apps.clients.forms import ClientTaskForm, CrmClientForm, LeadForm
from apps.galleries.forms import AlbumForm, DiscountCodeForm, GalleryForm, GallerySettingsForm, StoreProductForm, StoreSettingsForm
from apps.galleries.activity import log_gallery_activity
from apps.galleries.analytics import gallery_analytics_report
from apps.galleries.models import AccessToken, Album, AlbumPhoto, DiscountCode, Gallery, GalleryActivity, GalleryAnalyticsEvent, GalleryArchivePolicy, GalleryInvitation, GalleryOrder, GalleryPermission, GalleryPhoto, GallerySettings, GalleryStore, ProductVariant, StoreProduct
from apps.ai_engine.models import AIJob, AIProcessingStatus
from apps.dashboard.financial import financial_summary, format_currency
from apps.dashboard.financial_analytics import financial_analytics
from apps.dashboard.financial_operations import financial_operations
from apps.dashboard.financial_activity import TYPE_MAP, financial_activity
from apps.dashboard.financial_transactions import transaction_records
from apps.dashboard.financial_bulk import (EXPORT_COLUMNS, available_actions, csv_bytes, invoice_zip,
                                           run_bulk_action, selected_objects)
from apps.dashboard.financial_record_detail import financial_record_detail
from apps.dashboard.growth_analytics import (booking_value_by_source, growth_summary, lead_funnel,
                                             growth_opportunities, lead_source_performance, recent_growth_activity,
                                             referral_summary, reputation_summary, retention_summary, service_performance)
from apps.dashboard.financial_actions import add_credit, issue_refund, record_payment
from apps.dashboard.invoices import next_invoice_number, save_invoice
from apps.dashboard.analytics_overview import analytics_overview as build_analytics_overview
from apps.dashboard.models import GrowthCampaign, ReferralLink, ReviewRequest
from apps.dashboard.team_summary import authorized_studio, parse_team_filters, sessions_overlap, studio_sessions

WORKSPACE_MODULES = [
    {"key": "dashboard", "url_name": "dashboard", "icon": "bi-grid-1x2", "title": "Dashboard", "description": "Your business command center.", "coming_soon": False},
    {"key": "galleries", "url_name": "galleries", "icon": "bi-grid", "title": "Galleries", "description": "Organize, publish, and deliver photography collections.", "coming_soon": False},
    {"key": "all_galleries", "url_name": "all_galleries", "icon": "bi-images", "title": "All Galleries", "description": "Browse every photography collection.", "coming_soon": False},
    {"key": "gallery_archive", "url_name": "gallery_archive", "icon": "bi-archive", "title": "Gallery Archive", "description": "Recover inactive galleries and manage retention.", "coming_soon": False},
    {"key": "gallery_upload_queue", "url_name": "gallery_upload_queue", "icon": "bi-cloud-arrow-up", "title": "Upload Queue", "description": "Review gallery uploads and processing.", "coming_soon": False},
    {"key": "ai_processing", "url_name": "ai_processing", "icon": "bi-cpu", "title": "AI Processing", "description": "Monitor and manage gallery AI tasks.", "coming_soon": False},
    {"key": "clients", "url_name": "clients", "icon": "bi-people", "title": "Clients", "description": "Manage client relationships, invitations, and gallery access.", "coming_soon": True, "planned": ["Client records", "Invitations", "Gallery access"]},
    {"key": "events", "url_name": "events", "icon": "bi-calendar-event", "title": "Events", "description": "Manage photography events and event-code photo discovery.", "coming_soon": True, "planned": ["Event setup", "Event codes", "Photo discovery"]},
    {"key": "ai", "url_name": "ai", "icon": "bi-stars", "title": "AI Workspace", "description": "Future home for culling, editing assistance, search, tagging, and face recognition.", "coming_soon": True, "planned": ["Face recognition", "Image quality scoring", "Duplicate detection", "Blur detection", "Semantic search", "Auto-tagging", "AI editing assistance", "Watermark generation"]},
    {"key": "website", "url_name": "website", "icon": "bi-window", "title": "Client Website", "description": "Manage the photographer’s customer-facing homepage and branding.", "coming_soon": True, "planned": ["Brand preview", "Homepage sections", "Theme settings"]},
    {"key": "marketplace", "url_name": "marketplace", "icon": "bi-shop", "title": "Marketplace", "description": "Discover and sell products, services, or photography-related offerings.", "coming_soon": True, "planned": ["Offer listings", "Product discovery", "Sales channels"]},
    {"key": "orders", "url_name": "orders", "icon": "bi-bag-check", "title": "Orders", "description": "Track downloads, print purchases, and customer orders.", "coming_soon": True, "planned": ["Order history", "Print purchases", "Download tracking"]},
    {"key": "billing", "url_name": "billing", "icon": "bi-credit-card", "title": "Billing", "description": "Manage LumisPixel subscription and payment configuration.", "coming_soon": True, "planned": ["Subscription settings", "Payment configuration", "Invoices"]},
    {"key": "analytics", "url_name": "analytics", "icon": "bi-graph-up-arrow", "title": "Analytics", "description": "Review gallery activity, client engagement, sales, and business performance.", "coming_soon": False},
    {"key": "marketing", "url_name": "marketing", "icon": "bi-megaphone", "title": "Marketing", "description": "Manage promotions, outreach, and future campaign tools.", "coming_soon": True, "planned": ["Promotions", "Outreach", "Campaign tools"]},
    {"key": "profile", "url_name": "profile", "icon": "bi-person-badge", "title": "Profile", "description": "Review photographer and business information.", "coming_soon": False, "planned": ["Business details", "Contact information", "Specialties"]},
    {"key": "settings", "url_name": "settings", "icon": "bi-sliders", "title": "Settings", "description": "Manage workspace preferences, branding, notifications, and future theme switching.", "coming_soon": True, "planned": ["Workspace preferences", "Branding", "Notifications", "Future theme switching"]},
]
WORKSPACE_MODULES += [
    {"key": key, "url_name": key, "icon": "", "title": title, "description": f"{title} tools for your photography business are being prepared.", "coming_soon": True}
    for key, title in [
        ("crm", "CRM"), ("leads", "Leads"), ("ai_search", "AI Search"), ("albums", "Albums"),
        ("calendar", "Schedule"), ("bookings", "Bookings"), ("contracts", "Contracts"),
        ("financial_overview", "Financial Overview"), ("transactions", "Transactions"), ("growth", "Growth Overview"),
        ("invoices", "Invoices"), ("payments", "Payments"), ("revenue", "Revenue"),
        ("reviews", "Reviews"), ("referrals", "Referrals"), ("workflows", "Workflows"),
        ("ai_assistant", "AI Assistant"), ("team_overview", "Team Overview"),
        ("team_members", "Team Members"), ("team_performance", "Team Performance"), ("equipment", "Equipment"),
        ("tasks", "Tasks"), ("notifications", "Notifications"), ("help", "Help"),
    ]
]
next(module for module in WORKSPACE_MODULES if module["key"] == "calendar")["url_name"] = "schedule"
next(module for module in WORKSPACE_MODULES if module["key"] == "growth")["coming_soon"] = False
MODULE_BY_KEY = {m["key"]: m for m in WORKSPACE_MODULES}

NAVIGATION = [
    {"title": "", "icon": "bi-speedometer2", "items": [("dashboard", "Dashboard", "bi-grid-1x2")]},
    {"title": "Clients", "icon": "bi-people", "items": [("crm", "CRM", "bi-person-lines-fill"), ("leads", "Leads", "bi-funnel"), ("clients", "Clients", "bi-people-fill")]},
    {"title": "Bookings", "icon": "bi-calendar-check", "items": [("bookings", "Overview", "bi-grid-1x2"), ("calendar", "Schedule", "bi-calendar3")]},
    {"title": "Galleries", "icon": "bi-images", "items": [("galleries", "Dashboard", "bi-grid"), ("all_galleries", "Galleries", "bi-images")]},
    {"title": "Financial", "icon": "bi-wallet2", "items": [("financial_overview", "Overview", "bi-pie-chart"), ("transactions", "Transactions", "bi-arrow-left-right")]},
    {"title": "Growth", "icon": "bi-rocket-takeoff", "items": [("growth", "Overview", "bi-graph-up-arrow")]},
    {"title": "", "icon": "bi-bar-chart", "items": [("analytics", "Analytics", "bi-bar-chart-line")]},
    {"title": "Team", "icon": "bi-people", "items": [
        ("team_overview", "Overview", "bi-grid-1x2"),
        ("team_members", "Members", "bi-person-badge"),
        ("team_performance", "Performance", "bi-graph-up-arrow"),
    ]},
    {"title": "", "icon": "bi-gear", "items": [("settings", "Settings", "bi-gear")]},
]

# Legacy pages remain directly addressable, but highlight their consolidated workspace.
NAV_ACTIVE_ALIASES = {
    "invoices": "financial_overview", "revenue": "financial_overview",
    "payments": "transactions", "marketing": "growth", "reviews": "growth", "referrals": "growth",
    "schedule": "calendar",
    "gallery_archive": "all_galleries", "gallery_upload_queue": "all_galleries",
    "ai_processing": "all_galleries", "ai_search": "all_galleries", "albums": "all_galleries",
}
THEMES = {
    PhotographerProfile.WebsiteTheme.ELEGANT: ("Elegant", "A refined visual direction for weddings, portraits, family, and fine-art work.", "elegant"),
    PhotographerProfile.WebsiteTheme.MODERN_STUDIO: ("Modern Studio", "A clean studio presentation for commercial, branding, product, and headshot work.", "modern"),
    PhotographerProfile.WebsiteTheme.SPORTS_EVENTS: ("Sports & Events", "A high-energy direction for sports, schools, events, and high-volume photography.", "sports"),
}


def _reverse_module(module):
    return reverse(f"photographer_workspace:{module['url_name']}")


def _workspace_nav(active_key):
    active_key = NAV_ACTIVE_ALIASES.get(active_key, active_key)
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
    for group in NAVIGATION[1:]:
        groups.append({
            "title": group["title"],
            "icon": group["icon"],
            "items": [
                {"title": title, "icon": icon, "url": _reverse_module(MODULE_BY_KEY[key])}
                for key, title, icon in group["items"]
            ],
        })
    return groups


def _dashboard_context(request, active_key="dashboard", title="Dashboard"):
    profile = request.user.photographer_profile
    contract_booking = ClientSession.objects.filter(photographer=profile).order_by("-starts_at").first()
    contract_workspace_url = (
        f'{reverse("photographer_workspace:booking_detail", args=[contract_booking.pk])}?tab=contract#contract'
        if contract_booking else reverse("photographer_workspace:bookings")
    )
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
            {"label": "Pending Contracts", "count": 0, "icon": "bi-file-earmark-check", "summary": "No contracts await signatures.", "action": "View booking contract", "url": contract_workspace_url},
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
    if source == "__unknown__":
        leads = leads.filter(Q(lead_source="") | Q(lead_source__isnull=True))
    elif source:
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
    all_records = Gallery.objects.for_photographer(profile).active().select_related("client")
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
@require_GET
def gallery_archive(request):
    profile = request.user.photographer_profile
    records = Gallery.objects.for_photographer(profile).archived().select_related("client", "archived_by")
    query = request.GET.get("q", "").strip()
    reason, retention = request.GET.get("reason", ""), request.GET.get("retention", "")
    date_from, date_to = request.GET.get("date_from", ""), request.GET.get("date_to", "")
    storage, sort = request.GET.get("storage", ""), request.GET.get("sort", "recent")
    if query:
        records = records.filter(Q(name__icontains=query) | Q(client__first_name__icontains=query) | Q(client__last_name__icontains=query))
    if reason in Gallery.ArchiveReason.values:
        records = records.filter(archive_reason=reason)
    if retention in Gallery.RetentionType.values:
        records = records.filter(retention_type=retention)
    if date_from:
        records = records.filter(archived_at__date__gte=date_from)
    if date_to:
        records = records.filter(archived_at__date__lte=date_to)
    size_filters = {"small": (0, 1024**3), "medium": (1024**3, 10 * 1024**3), "large": (10 * 1024**3, None)}
    if storage in size_filters:
        low, high = size_filters[storage]
        records = records.filter(storage_used__gte=low)
        if high:
            records = records.filter(storage_used__lt=high)
    ordering = {"recent": "-archived_at", "oldest": "archived_at", "name": "name", "storage": "-storage_used", "deletion": "scheduled_deletion_at"}
    records = records.order_by(ordering.get(sort, "-archived_at"))
    page = Paginator(records, 10).get_page(request.GET.get("page"))
    retained_query = request.GET.copy(); retained_query.pop("page", None)
    all_archived = Gallery.objects.for_photographer(profile).archived()
    policy, _ = GalleryArchivePolicy.objects.get_or_create(photographer=profile)
    context = _dashboard_context(request, "gallery_archive", "Gallery Archive")
    context.update({
        "archive_page": page, "archive_query": query, "selected_reason": reason, "selected_retention": retention,
        "selected_date_from": date_from, "selected_date_to": date_to, "selected_storage": storage, "selected_sort": sort,
        "archive_reasons": Gallery.ArchiveReason.choices, "retention_choices": Gallery.RetentionType.choices,
        "active_galleries": Gallery.objects.for_photographer(profile).active().order_by("name"), "policy": policy,
        "retained_query": retained_query.urlencode(), "has_filters": any([query, reason, retention, date_from, date_to, storage]),
        "archive_metrics": [
            ("Archived Galleries", all_archived.count(), "bi-archive", "Available to restore"),
            ("Archived Photos", all_archived.aggregate(total=Coalesce(Sum("image_count"), 0))["total"], "bi-images", "Relationships preserved"),
            ("Storage Used", all_archived.aggregate(total=Coalesce(Sum("storage_used"), 0))["total"], "bi-device-ssd", "bytes"),
            ("Scheduled for Deletion", all_archived.filter(retention_type__in=[Gallery.RetentionType.SCHEDULED, Gallery.RetentionType.DELETION_PENDING]).count(), "bi-clock-history", "Review before removal"),
        ],
    })
    return render(request, "photographer_workspace/galleries/archive.html", context)


@photographer_workspace_required
@require_POST
def gallery_archive_actions(request):
    profile = request.user.photographer_profile
    ids = request.POST.getlist("gallery_ids")
    records = Gallery.objects.for_photographer(profile).filter(pk__in=ids, deleted_at__isnull=True)
    action = request.POST.get("action")
    if action == "save_policy":
        policy, _ = GalleryArchivePolicy.objects.get_or_create(photographer=profile)
        policy.archive_delivered = bool(request.POST.get("archive_delivered"))
        policy.archive_after_expiration = bool(request.POST.get("archive_after_expiration"))
        policy.warn_before_deletion = bool(request.POST.get("warn_before_deletion"))
        policy.inactivity_days = int(request.POST["inactivity_days"]) if request.POST.get("inactivity_days", "").isdigit() else None
        policy.default_retention_days = int(request.POST.get("default_retention_days", 365))
        policy.save()
        messages.success(request, "Archive policies saved.")
        return redirect("photographer_workspace:gallery_archive")
    if not ids:
        messages.error(request, "Select at least one gallery.")
        return redirect("photographer_workspace:gallery_archive")
    now = timezone.now()
    if action == "download":
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for gallery in records.archived().prefetch_related("photos"):
                manifest = f"Gallery: {gallery.name}\nPhotos: {gallery.image_count}\nArchived: {gallery.archived_at}\nReason: {gallery.get_archive_reason_display()}\n"
                bundle.writestr(f"{slugify(gallery.name)}/archive-info.txt", manifest)
                for photo in gallery.photos.all():
                    if photo.file:
                        with photo.file.open("rb") as source:
                            bundle.writestr(f"{slugify(gallery.name)}/photos/{photo.original_name}", source.read())
        archive.seek(0)
        return FileResponse(archive, as_attachment=True, filename="lumispixel-gallery-archive.zip", content_type="application/zip")
    if action == "archive" and request.POST.get("confirm_archive"):
        reason = request.POST.get("archive_reason")
        if reason not in Gallery.ArchiveReason.values:
            messages.error(request, "Choose an archive reason.")
            return redirect("photographer_workspace:gallery_archive")
        days = int(request.POST.get("retention_days", 365))
        for gallery in records:
            gallery.previous_status = gallery.status
            gallery.status, gallery.archived_at, gallery.archived_by = Gallery.Status.ARCHIVED, now, request.user
            gallery.archive_reason = reason
            gallery.visibility = Gallery.Visibility.PRIVATE if request.POST.get("disable_public_access") else gallery.visibility
            gallery.retention_type = Gallery.RetentionType.INDEFINITE if days == 0 else Gallery.RetentionType.UNTIL_DATE
            gallery.retention_until = None if days == 0 else (now + timedelta(days=days)).date()
            gallery.save()
            log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_ARCHIVED, description="Gallery archived; albums, photos, and history were preserved.", actor=request.user)
        messages.success(request, f"Archived {records.count()} gallery records.")
    elif action == "restore":
        for gallery in records.archived():
            restored_status = gallery.previous_status if gallery.previous_status and gallery.previous_status != Gallery.Status.PUBLISHED else Gallery.Status.DRAFT
            gallery.status, gallery.archived_at, gallery.scheduled_deletion_at = restored_status, None, None
            gallery.archived_by, gallery.archive_reason, gallery.retention_until = None, "", None
            gallery.visibility = Gallery.Visibility.PRIVATE
            gallery.save()
            log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_UPDATED, title="Gallery restored", description="Restored without publishing. Visibility and expiration settings require review.", actor=request.user)
        messages.success(request, "Gallery restored privately. Review visibility and expiration before publishing.")
    elif action == "retention":
        retention_type = request.POST.get("retention_type")
        if retention_type not in Gallery.RetentionType.values:
            messages.error(request, "Choose a valid retention status.")
            return redirect("photographer_workspace:gallery_archive")
        until = request.POST.get("retention_until") or None
        records.archived().update(retention_type=retention_type, retention_until=until,
            scheduled_deletion_at=timezone.make_aware(timezone.datetime.fromisoformat(until)) if until and retention_type in [Gallery.RetentionType.SCHEDULED, Gallery.RetentionType.DELETION_PENDING] else None)
        messages.success(request, "Retention settings updated.")
    elif action == "permanent_delete":
        gallery = records.archived().first()
        if not gallery or len(ids) != 1 or request.POST.get("gallery_name") != gallery.name or not request.POST.get("acknowledge_delete"):
            messages.error(request, "Permanent deletion requires the exact gallery name and explicit acknowledgment.")
        elif gallery.orders.exists():
            gallery.deleted_at = now; gallery.save(update_fields=["deleted_at", "updated_at"])
            messages.warning(request, "Gallery access was removed, but required financial transaction history was retained.")
        else:
            gallery.deleted_at = now; gallery.save(update_fields=["deleted_at", "updated_at"])
            gallery.delete()
            messages.success(request, "Gallery and associated non-financial records permanently deleted.")
    return redirect("photographer_workspace:gallery_archive")


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
        log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_CREATED,
                             description=f"{gallery.name} was created and its workspace is ready.", actor=request.user)
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
        previous = {"name": gallery.name, "status": gallery.status, "visibility": gallery.visibility}
        gallery = form.save(commit=False)
        gallery.slug = _unique_gallery_slug(profile, gallery.name, gallery.pk)
        gallery.full_clean()
        gallery.save()
        log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_UPDATED,
                             description="Gallery details were updated.", actor=request.user,
                             metadata={"previous_value": previous, "new_value": {"name": gallery.name, "status": gallery.status, "visibility": gallery.visibility}})
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
        now = timezone.now()
        for gallery in records:
            gallery.previous_status = gallery.status
            gallery.status = Gallery.Status.ARCHIVED
            gallery.archived_at = now
            gallery.archived_by = request.user
            gallery.archive_reason = Gallery.ArchiveReason.OTHER
            gallery.visibility = Gallery.Visibility.PRIVATE
            gallery.save()
            log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_ARCHIVED,
                                 description="Gallery archived from the gallery list.", actor=request.user)
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
            log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.PHOTOS_UPLOADED,
                                 description=f"{len(created)} photo{'s' if len(created) != 1 else ''} uploaded successfully.", actor=request.user,
                                 metadata={"count": len(created), "files": [item["name"] for item in created[:10]]})
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
@require_http_methods(["GET", "POST"])
def gallery_workspace(request, pk):
    gallery = get_object_or_404(
        Gallery.objects.for_photographer(request.user.photographer_profile).select_related("client"), pk=pk
    )
    context = _dashboard_context(request, "all_galleries", gallery.name)
    tab = request.GET.get("tab", "overview")
    tabs = ("overview", "photos", "albums", "ai-tools", "client-access", "store", "downloads", "activity", "settings")
    if tab not in tabs:
        tab = "overview"
    permissions, _ = GalleryPermission.objects.get_or_create(gallery=gallery)
    settings, _ = GallerySettings.objects.get_or_create(gallery=gallery, defaults={"gallery_url": gallery.slug})
    store, _ = GalleryStore.objects.get_or_create(gallery=gallery, defaults={"photographer": request.user.photographer_profile, "name": f"{gallery.name} Store"})
    store_form = StoreSettingsForm(request.POST or None, instance=store, prefix="store")
    discount_form = DiscountCodeForm(request.POST or None, prefix="discount")
    settings_form = GallerySettingsForm(request.POST or None, request.FILES or None, instance=settings,
                                        photographer=request.user.photographer_profile, prefix="settings")
    general_form = GalleryForm(request.POST or None, request.FILES or None, instance=gallery,
                               photographer=request.user.photographer_profile, prefix="general")
    general_form.fields["status"].choices = [(value, label) for value, label in Gallery.Status.choices
                                               if value in {Gallery.Status.DRAFT, Gallery.Status.PUBLISHED, Gallery.Status.ARCHIVED}]
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_store":
            if store_form.is_valid():
                configured = store_form.save(commit=False); configured.photographer = request.user.photographer_profile; configured.gallery = gallery
                configured.full_clean(); configured.save(); messages.success(request, "Store settings saved.")
            else: messages.error(request, "Review the highlighted store settings.")
            tab = "store"
        elif action == "add_discount":
            if discount_form.is_valid():
                discount = discount_form.save(commit=False); discount.photographer = request.user.photographer_profile; discount.gallery = gallery
                discount.full_clean(); discount.save(); messages.success(request, "Discount code created.")
            else: messages.error(request, "Review the discount code details.")
            tab = "store"
        elif action == "toggle_store":
            store.enabled = not store.enabled; store.save(update_fields=["enabled", "updated_at"])
            messages.success(request, f"Store {'enabled' if store.enabled else 'disabled'}.")
            return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[gallery.pk])}?tab=store")
        elif action == "save_settings":
            if general_form.is_valid() and settings_form.is_valid():
                with transaction.atomic():
                    updated_gallery = general_form.save(commit=False)
                    updated_gallery.slug = _unique_gallery_slug(request.user.photographer_profile, updated_gallery.name, gallery.pk)
                    if updated_gallery.status == Gallery.Status.PUBLISHED and not updated_gallery.published_at:
                        updated_gallery.published_at = timezone.now()
                    updated_gallery.full_clean()
                    updated_gallery.save()
                    updated_settings = settings_form.save(commit=False)
                    updated_settings.gallery = updated_gallery
                    updated_settings.full_clean()
                    updated_settings.save()
                messages.success(request, "Gallery settings saved.")
                return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[gallery.pk])}?tab=settings")
            tab = "settings"
            messages.error(request, "Review the highlighted settings and try again.")
        elif action in {"archive_gallery", "duplicate_gallery", "delete_gallery"}:
            if action == "delete_gallery":
                gallery.delete()
                messages.success(request, "Gallery permanently deleted.")
                return redirect("photographer_workspace:all_galleries")
            if action == "archive_gallery":
                gallery.status = Gallery.Status.ARCHIVED
                gallery.save(update_fields=["status", "updated_at"])
                messages.success(request, "Gallery archived.")
            else:
                with transaction.atomic():
                    duplicate = Gallery.objects.get(pk=gallery.pk)
                    duplicate.pk = None
                    duplicate.name = f"{gallery.name} Copy"
                    duplicate.slug = _unique_gallery_slug(request.user.photographer_profile, duplicate.name)
                    duplicate.status = Gallery.Status.DRAFT
                    duplicate.published_at = None
                    duplicate.save()
                    copied_settings = GallerySettings.objects.get(pk=settings.pk)
                    copied_settings.pk = None
                    copied_settings.gallery = duplicate
                    copied_settings.gallery_url = duplicate.slug
                    copied_settings.save()
                messages.success(request, "Gallery duplicated as a draft.")
            return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[gallery.pk])}?tab=settings")
        elif action == "save_access":
            visibility = request.POST.get("visibility")
            if visibility in Gallery.Visibility.values:
                gallery.visibility = visibility
            expiration = request.POST.get("expiration_date")
            gallery.expires_at = timezone.make_aware(timezone.datetime.fromisoformat(expiration)) if expiration else None
            gallery.save(update_fields=["visibility", "expires_at", "updated_at"])
            boolean_fields = ("view_gallery", "download_images", "download_originals", "favorite_photos", "comment", "share_gallery", "purchase_prints", "automatic_gallery_lock")
            for field in boolean_fields:
                setattr(permissions, field, field in request.POST)
            watermark = request.POST.get("watermark")
            if watermark in GalleryPermission.Watermark.values:
                permissions.watermark = watermark
            download_expiration = request.POST.get("download_expiration")
            permissions.download_expires_at = timezone.make_aware(timezone.datetime.fromisoformat(download_expiration)) if download_expiration else None
            permissions.save()
            log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.PERMISSION_CHANGED,
                                 description="Client access permissions were updated.", actor=request.user,
                                 related_object=permissions, metadata={"new_value": {"visibility": gallery.visibility, "watermark": permissions.watermark}})
            messages.success(request, "Client access settings saved.")
        elif action == "invite":
            name, email = request.POST.get("client_name", "").strip(), request.POST.get("email", "").strip().lower()
            if name and email:
                invitation, created = GalleryInvitation.objects.get_or_create(gallery=gallery, email=email, defaults={"client_name": name})
                if not created:
                    invitation.client_name, invitation.status, invitation.resent_at = name, GalleryInvitation.Status.PENDING, timezone.now()
                    invitation.save(update_fields=["client_name", "status", "resent_at"])
                AccessToken.objects.filter(invitation=invitation, revoked_at__isnull=True).update(revoked_at=timezone.now())
                AccessToken.issue(invitation, expires_at=gallery.expires_at)
                log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.CLIENT_INVITED,
                                     description=f"An invitation was prepared for {name}.", actor=request.user,
                                     related_object=invitation, metadata={"client": name})
                messages.success(request, "Invitation prepared. Email delivery can be connected later.")
            else:
                messages.error(request, "Enter a client name and email address.")
        elif action in {"resend", "disable", "remove"}:
            invitation = get_object_or_404(gallery.invitations, pk=request.POST.get("invitation_id"))
            if action == "remove":
                invitation.delete()
                messages.success(request, "Invitation removed.")
            elif action == "disable":
                invitation.status = GalleryInvitation.Status.DISABLED
                invitation.save(update_fields=["status"])
                invitation.access_tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
                messages.success(request, "Client access disabled.")
            else:
                invitation.resent_at = timezone.now()
                invitation.status = GalleryInvitation.Status.PENDING
                invitation.save(update_fields=["resent_at", "status"])
                invitation.access_tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
                AccessToken.issue(invitation, expires_at=gallery.expires_at)
                messages.success(request, "A fresh invitation is ready for future email delivery.")
        if action not in {"save_settings", "save_store", "add_discount"}:
            return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[gallery.pk])}?tab=client-access")
    photos = gallery.photos.all()
    query = request.GET.get("q", "").strip()
    if query:
        photos = photos.filter(original_name__icontains=query)
    photos = photos.order_by("original_name" if request.GET.get("sort") == "name" else "-created_at")
    albums = gallery.albums.annotate(photo_count=Count("photos"))
    invitations = gallery.invitations.all()
    paid_orders = store.orders.filter(payment_status__in=[GalleryOrder.Status.PAID, GalleryOrder.Status.COMPLETED])
    revenue = paid_orders.aggregate(value=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField(max_digits=10, decimal_places=2)))["value"]
    orders_page = Paginator(store.orders.prefetch_related("items"), 10).get_page(request.GET.get("orders_page"))
    products_page = Paginator(store.products.prefetch_related("variants"), 8).get_page(request.GET.get("products_page"))
    all_activity = GalleryActivity.objects.for_photographer(request.user.photographer_profile).filter(gallery=gallery)
    activity = all_activity.select_related("actor")
    activity_query, activity_type = request.GET.get("activity_q", "").strip(), request.GET.get("activity_type", "")
    activity_user, activity_source = request.GET.get("activity_user", ""), request.GET.get("activity_source", "")
    activity_start, activity_end = request.GET.get("activity_start", ""), request.GET.get("activity_end", "")
    if activity_query: activity = activity.filter(Q(title__icontains=activity_query) | Q(description__icontains=activity_query) | Q(related_object_type__icontains=activity_query))
    if activity_type in GalleryActivity.EventType.values: activity = activity.filter(event_type=activity_type)
    if activity_user == "system": activity = activity.filter(actor_type=GalleryActivity.ActorType.SYSTEM)
    elif activity_user.isdigit(): activity = activity.filter(actor_id=activity_user)
    if activity_source: activity = activity.filter(related_object_type__iexact=activity_source)
    if activity_start: activity = activity.filter(created_at__date__gte=activity_start)
    if activity_end: activity = activity.filter(created_at__date__lte=activity_end)
    if tab == "activity" and request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{gallery.slug}-activity.csv"'
        writer = csv.writer(response); writer.writerow(["Date", "Event", "Description", "Actor", "Source", "Related record"])
        for event in activity.iterator(): writer.writerow([event.created_at.isoformat(), event.title, event.description, event.actor.full_name if event.actor else "System", event.actor_type, f"{event.related_object_type} {event.related_object_id}"])
        return response
    activity_page = Paginator(activity, 12).get_page(request.GET.get("activity_page"))
    today, grouped_activity = timezone.localdate(), []
    for event in activity_page:
        event_date = timezone.localtime(event.created_at).date()
        label = "Today" if event_date == today else "Yesterday" if event_date == today - timezone.timedelta(days=1) else "Earlier this week" if (today - event_date).days < 7 else event_date.strftime("%B %d, %Y").replace(" 0", " ")
        if not grouped_activity or grouped_activity[-1][0] != label: grouped_activity.append([label, []])
        grouped_activity[-1][1].append(event)
    context.update({"gallery": gallery, "active_tab": tab, "photos": photos, "albums": albums,
                    "store": store, "store_form": store_form, "discount_form": discount_form, "products": products_page, "orders": orders_page,
                    "discounts": gallery.discount_codes.all(), "store_summary": {"revenue": revenue, "orders": store.orders.count(), "average": revenue / paid_orders.count() if paid_orders.count() else Decimal("0.00"), "products": store.products.filter(active=True).count()},
                    "general_form": general_form, "settings_form": settings_form,
                    "gallery_permissions": permissions, "invitations": invitations,
                    "access_summary": {"invited": invitations.count(), "sessions": invitations.filter(status=GalleryInvitation.Status.ACTIVE).count(), "downloads": gallery.download_count, "shares": 0},
                    "permission_options": [(field, label, getattr(permissions, field)) for field, label in (
                        ("view_gallery", "View Gallery"), ("download_images", "Download Images"),
                        ("download_originals", "Download Originals"), ("favorite_photos", "Favorite Photos"),
                        ("comment", "Comment"), ("share_gallery", "Share Gallery"),
                        ("purchase_prints", "Purchase Prints"),
                    )], "watermark_options": GalleryPermission.Watermark.choices,
                    "album_summary": [
                        {"label": "Total Albums", "value": albums.count(), "icon": "bi-collection"},
                        {"label": "Public Albums", "value": albums.filter(visibility=Album.Visibility.PUBLIC).count(), "icon": "bi-globe2"},
                        {"label": "Private Albums", "value": albums.filter(visibility=Album.Visibility.CLIENT_ONLY).count(), "icon": "bi-people"},
                        {"label": "Hidden Albums", "value": albums.filter(visibility=Album.Visibility.HIDDEN).count(), "icon": "bi-eye-slash"},
                    ], "storage_display": _format_storage(gallery.storage_used), "upload_percent": 100 if gallery.image_count else 0,
                    "activity_page": activity_page, "grouped_activity": grouped_activity, "activity_types": GalleryActivity.EventType.choices,
                    "activity_actors": all_activity.filter(actor__isnull=False).values("actor_id", "actor__first_name", "actor__last_name", "actor__email").distinct(),
                    "activity_sources": all_activity.exclude(related_object_type="").values_list("related_object_type", flat=True).distinct().order_by("related_object_type"),
                    "activity_summary": {"total": all_activity.count(), "clients": all_activity.filter(actor_type=GalleryActivity.ActorType.CLIENT).count(), "downloads": all_activity.filter(event_type__in=[GalleryActivity.EventType.PHOTO_DOWNLOADED, GalleryActivity.EventType.GALLERY_DOWNLOADED]).count(), "store": all_activity.filter(event_type__in=[GalleryActivity.EventType.STORE_ORDER_CREATED, GalleryActivity.EventType.PAYMENT_CHANGED]).count()},
                    "activity_has_filters": any([activity_query, activity_type, activity_user, activity_source, activity_start, activity_end])})
    return render(request, "photographer_workspace/galleries/workspace.html", context)


@photographer_workspace_required
@require_GET
def gallery_analytics(request, pk):
    profile = request.user.photographer_profile
    gallery = get_object_or_404(Gallery.objects.for_photographer(profile), pk=pk)
    def parsed_date(name):
        try:
            return timezone.datetime.fromisoformat(request.GET.get(name, "")).date()
        except ValueError:
            return None
    report = gallery_analytics_report(
        gallery=gallery, start=parsed_date("start"), end=parsed_date("end"),
        album_id=request.GET.get("album") if request.GET.get("album", "").isdigit() else None,
        device=request.GET.get("device", ""), visitor_type=request.GET.get("visitor_type", "all"),
    )
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{gallery.slug}-analytics.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Gallery views", "Unique visitors", "Downloads", "Favorites"])
        for day in report["days"]:
            writer.writerow([day["date"], day["views"], day["visitors"], day["downloads"], day["favorites"]])
        return response
    context = _dashboard_context(request, "all_galleries", "Gallery Analytics")
    context.update({"gallery": gallery, "report": report, "albums": gallery.albums.only("id", "name"),
                    "device_choices": GalleryAnalyticsEvent.Device.choices})
    return render(request, "photographer_workspace/galleries/analytics.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def store_product_form(request, gallery_pk, pk=None):
    profile = request.user.photographer_profile
    gallery = get_object_or_404(Gallery.objects.for_photographer(profile), pk=gallery_pk)
    store, _ = GalleryStore.objects.get_or_create(gallery=gallery, defaults={"photographer": profile, "name": f"{gallery.name} Store"})
    product = get_object_or_404(StoreProduct.objects.filter(photographer=profile, gallery=gallery), pk=pk) if pk else None
    form = StoreProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            product = form.save(commit=False); product.store=store; product.gallery=gallery; product.photographer=profile; product.full_clean(); product.save()
            product.variants.all().delete()
            ProductVariant.objects.bulk_create([ProductVariant(product=product, name=name.strip(), display_order=i) for i, name in enumerate(form.cleaned_data["variants"].splitlines()) if name.strip()])
        messages.success(request, "Product saved.")
        return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[gallery.pk])}?tab=store")
    context = _dashboard_context(request, "all_galleries", "Edit Product" if product else "Add Product")
    context.update({"gallery":gallery, "product":product, "form":form})
    return render(request, "photographer_workspace/galleries/product_form.html", context)


@photographer_workspace_required
@require_POST
def store_product_action(request, pk):
    product = get_object_or_404(StoreProduct.objects.filter(photographer=request.user.photographer_profile), pk=pk)
    action = request.POST.get("action")
    if action == "delete": product.delete(); messages.success(request, "Product deleted.")
    elif action == "toggle": product.active=not product.active; product.save(update_fields=["active", "updated_at"])
    elif action == "duplicate":
        variants=list(product.variants.all()); product.pk=None; product.name += " Copy"; product.active=False; product.save()
        ProductVariant.objects.bulk_create([ProductVariant(product=product,name=v.name,price_adjustment=v.price_adjustment,display_order=v.display_order) for v in variants])
    return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[product.gallery_id])}?tab=store")


@photographer_workspace_required
def gallery_order_detail(request, pk):
    order = get_object_or_404(GalleryOrder.objects.filter(photographer=request.user.photographer_profile).select_related("gallery").prefetch_related("items__selected_photos"), pk=pk)
    context=_dashboard_context(request,"all_galleries",order.order_number); context["order"]=order
    return render(request,"photographer_workspace/galleries/order_detail.html",context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def create_album(request, gallery_pk):
    gallery = get_object_or_404(Gallery.objects.for_photographer(request.user.photographer_profile), pk=gallery_pk)
    form = AlbumForm(request.POST or None, request.FILES or None, gallery=gallery)
    if request.method == "POST" and form.is_valid():
        album = form.save(commit=False)
        album.gallery = gallery
        album.full_clean()
        album.save()
        log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.ALBUM_CREATED,
                             description=f"The album {album.name} was created.", actor=request.user, related_object=album)
        messages.success(request, "Album created. Add photos when you're ready.")
        return redirect("photographer_workspace:album_workspace", pk=album.pk)
    context = _dashboard_context(request, "all_galleries", "Create Album")
    context.update({"form": form, "gallery": gallery, "form_title": "Create Album", "submit_label": "Create Album"})
    return render(request, "photographer_workspace/galleries/album_form.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_album(request, pk):
    album = get_object_or_404(Album.objects.for_photographer(request.user.photographer_profile).select_related("gallery"), pk=pk)
    form = AlbumForm(request.POST or None, request.FILES or None, instance=album, gallery=album.gallery)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_gallery_activity(gallery=album.gallery, event_type=GalleryActivity.EventType.ALBUM_UPDATED,
                             description=f"The album {album.name} was updated.", actor=request.user, related_object=album)
        messages.success(request, "Album updated.")
        return redirect("photographer_workspace:album_workspace", pk=album.pk)
    context = _dashboard_context(request, "all_galleries", "Edit Album")
    context.update({"form": form, "gallery": album.gallery, "album": album, "form_title": "Edit Album", "submit_label": "Save Changes"})
    return render(request, "photographer_workspace/galleries/album_form.html", context)


@photographer_workspace_required
@require_GET
def album_workspace(request, pk):
    album = get_object_or_404(Album.objects.for_photographer(request.user.photographer_profile).select_related("gallery", "cover_photo"), pk=pk)
    memberships = album.album_photos.select_related("photo")
    query = request.GET.get("q", "").strip()
    if query:
        memberships = memberships.filter(photo__original_name__icontains=query)
    ordering = {"newest": "-photo__created_at", "name": "photo__original_name", "order": "position"}
    memberships = memberships.order_by(ordering.get(request.GET.get("sort"), "position"))
    other_albums = album.gallery.albums.exclude(pk=album.pk)
    context = _dashboard_context(request, "all_galleries", album.name)
    context.update({"album": album, "gallery": album.gallery, "memberships": memberships, "other_albums": other_albums})
    return render(request, "photographer_workspace/galleries/album_workspace.html", context)


@photographer_workspace_required
@require_POST
def album_action(request, pk):
    album = get_object_or_404(Album.objects.for_photographer(request.user.photographer_profile).select_related("gallery"), pk=pk)
    action = request.POST.get("action")
    if action == "delete":
        gallery_pk = album.gallery_id
        album.delete()
        messages.success(request, "Album deleted. Your gallery photos were not removed.")
        return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[gallery_pk])}?tab=albums")
    if action == "duplicate":
        source_memberships = list(album.album_photos.all())
        original_name = album.name
        album.pk = None
        album.name = f"{original_name} Copy"
        album.cover_image = ""
        album.save()
        AlbumPhoto.objects.bulk_create([AlbumPhoto(album=album, photo_id=item.photo_id, position=item.position) for item in source_memberships])
        messages.success(request, "Album duplicated.")
        return redirect("photographer_workspace:album_workspace", pk=album.pk)
    return JsonResponse({"error": "Unsupported action."}, status=400)


@photographer_workspace_required
@require_POST
def album_photo_action(request, pk):
    album = get_object_or_404(Album.objects.for_photographer(request.user.photographer_profile).select_related("gallery"), pk=pk)
    photo_ids = request.POST.getlist("photo_ids")
    photos = GalleryPhoto.objects.filter(gallery=album.gallery, pk__in=photo_ids)
    action = request.POST.get("action")
    if action == "remove":
        album.album_photos.filter(photo__in=photos).delete()
    elif action == "cover" and photos.count() == 1:
        album.cover_photo = photos.first()
        album.save(update_fields=["cover_photo", "updated_at"])
    elif action == "move":
        target = get_object_or_404(album.gallery.albums, pk=request.POST.get("target_album"))
        with transaction.atomic():
            existing = set(target.photos.filter(pk__in=photo_ids).values_list("pk", flat=True))
            start = target.album_photos.aggregate(Max("position"))["position__max"] or 0
            AlbumPhoto.objects.bulk_create([AlbumPhoto(album=target, photo=photo, position=start + index) for index, photo in enumerate(photos, 1) if photo.pk not in existing])
            album.album_photos.filter(photo__in=photos).delete()
    else:
        return JsonResponse({"error": "Choose valid photos and an action."}, status=400)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Album photos updated.")
    return redirect("photographer_workspace:album_workspace", pk=album.pk)


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
@require_http_methods(["GET", "POST"])
def bookings_dashboard(request):
    """Render the lightweight bookings command view without introducing booking models."""
    profile = request.user.photographer_profile
    if request.method == "POST":
        if request.POST.get("action") == "mark_complete":
            session = get_object_or_404(
                ClientSession.objects.filter(photographer=profile).exclude(status=ClientSession.Status.CANCELLED),
                pk=request.POST.get("session_id"),
            )
            session.status = ClientSession.Status.COMPLETED
            session.save(update_fields=["status"])
            messages.success(request, f"{session.session_type} for {session.client} marked complete.")
        return redirect("photographer_workspace:bookings")

    now = timezone.now()
    range_key = request.GET.get("range", "30")
    range_options = {"7": "Next 7 days", "30": "Next 30 days", "90": "Next 90 days", "all": "All upcoming"}
    if range_key not in range_options:
        range_key = "30"

    sessions = ClientSession.objects.filter(
        photographer=profile, starts_at__gte=now,
    ).exclude(status=ClientSession.Status.CANCELLED).select_related("client")
    status = request.GET.get("status", "")
    if status in ClientSession.Status.values:
        sessions = sessions.filter(status=status)
    if range_key != "all":
        sessions = sessions.filter(starts_at__lt=now + timedelta(days=int(range_key)))
    contract_booking = sessions.order_by("starts_at").first()
    contract_workspace_url = (
        f'{reverse("photographer_workspace:booking_detail", args=[contract_booking.pk])}?tab=contract#contract'
        if contract_booking else reverse("photographer_workspace:bookings")
    )

    today_sessions = ClientSession.objects.filter(
        photographer=profile,
        starts_at__date=timezone.localdate(),
    ).exclude(status=ClientSession.Status.CANCELLED).select_related("client").order_by("starts_at")
    for session in today_sessions:
        session.ends_at = session.starts_at + timedelta(hours=1, minutes=30)

    open_invoices = ClientInvoice.objects.filter(photographer=profile).exclude(
        status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID]
    )
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=DecimalField(max_digits=12, decimal_places=2))
    outstanding = open_invoices.aggregate(
        total=Coalesce(Sum(balance), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    inquiries = Lead.objects.for_photographer(profile).filter(
        archived_at__isnull=True, status__in=[Lead.Status.NEW, Lead.Status.CONTACTED]
    )
    all_leads = Lead.objects.for_photographer(profile).filter(archived_at__isnull=True)
    new_inquiries = all_leads.filter(status=Lead.Status.NEW).count()
    paid_revenue = ClientInvoice.objects.filter(photographer=profile).aggregate(
        total=Coalesce(Sum("amount_paid"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    month_start = timezone.localdate().replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    monthly_invoices = ClientInvoice.objects.filter(
        photographer=profile, created_at__date__gte=month_start,
    ).exclude(status=ClientInvoice.Status.VOID)
    previous_invoices = ClientInvoice.objects.filter(
        photographer=profile,
        created_at__date__range=(previous_month_start, previous_month_end),
    ).exclude(status=ClientInvoice.Status.VOID)
    monthly_booked = monthly_invoices.aggregate(
        total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    monthly_collected = monthly_invoices.aggregate(
        total=Coalesce(Sum("amount_paid"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    previous_booked = previous_invoices.aggregate(
        total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"]
    monthly_average = monthly_booked / monthly_invoices.count() if monthly_invoices.count() else Decimal("0.00")
    period_change = ((monthly_booked - previous_booked) / previous_booked * 100) if previous_booked else None

    # ClientInvoice currently has no service/category field. Session names provide
    # the best server-rendered breakdown until a first-class Booking model lands.
    session_categories = {name: 0 for name in ("Weddings", "Portraits", "Events", "Commercial", "Other")}
    for session_type in ClientSession.objects.filter(photographer=profile).values_list("session_type", flat=True):
        normalized = session_type.lower()
        category = next((name for name in session_categories if name[:-1].lower() in normalized), "Other")
        session_categories[category] += 1
    category_total = sum(session_categories.values())
    session_breakdown = [
        {"label": label, "count": count, "percent": round(count / category_total * 100) if category_total else 0}
        for label, count in session_categories.items()
    ]

    # Six compact points keep the chart dependency-free and reusable. Values are
    # derived from invoice records rather than embedded presentation data.
    revenue_chart = []
    for offset in range(5, -1, -1):
        point_start = month_start
        for _ in range(offset):
            point_start = (point_start - timedelta(days=1)).replace(day=1)
        next_month = (point_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        point_end = min(next_month - timedelta(days=1), timezone.localdate())
        point_value = ClientInvoice.objects.filter(
            photographer=profile, created_at__date__gte=point_start,
            created_at__date__lte=point_end,
        ).exclude(status=ClientInvoice.Status.VOID).aggregate(
            total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField())
        )["total"]
        revenue_chart.append({"label": point_start.strftime("%b"), "value": point_value})
    chart_max = max((point["value"] for point in revenue_chart), default=Decimal("0.00")) or Decimal("1.00")
    for index, point in enumerate(revenue_chart):
        point["x"] = 8 + index * 18
        point["y"] = round(88 - float(point["value"] / chart_max) * 72, 2)

    activity_styles = {
        ClientActivity.EventType.LEAD_CREATED: ("bi-envelope-plus", "inquiry"),
        ClientActivity.EventType.LEAD_BOOKED: ("bi-calendar2-check", "booking"),
        ClientActivity.EventType.CONTRACT_SIGNED: ("bi-pen", "contract"),
        ClientActivity.EventType.PAYMENT_RECEIVED: ("bi-credit-card", "payment"),
        ClientActivity.EventType.CONSULTATION_SCHEDULED: ("bi-calendar-event", "schedule"),
        ClientActivity.EventType.GALLERY_DELIVERED: ("bi-images", "gallery"),
    }
    recent_activity = []
    for activity in ClientActivity.objects.filter(photographer=profile).select_related("lead", "client")[:7]:
        icon, tone = activity_styles.get(activity.event_type, ("bi-activity", "default"))
        related = str(activity.client or activity.lead or "Booking workspace")
        recent_activity.append({"icon": icon, "tone": tone, "description": activity.description or activity.get_event_type_display(), "related": related, "occurred_at": activity.occurred_at})
    conversion_rate = all_leads.conversion_rate()

    # Keep the pipeline useful even while the surrounding booking modules are
    # being connected: every stage is calculated from the photographer's own
    # inquiry records and links back to the existing filtered leads view.
    pipeline_rows = {
        row["status"]: row
        for row in all_leads.values("status").annotate(
            count=Count("id"),
            value=Coalesce(
                Sum("estimated_value"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
    }
    inquiry_pipeline = [
        {
            "key": key,
            "label": "Proposal Sent" if key == Lead.Status.PROPOSAL_SENT else label,
            "count": pipeline_rows.get(key, {}).get("count", 0),
            "value": pipeline_rows.get(key, {}).get("value", Decimal("0.00")),
            "url": f"{reverse('photographer_workspace:leads')}?status={key}",
        }
        for key, label in Lead.Status.choices
    ]
    responded_leads = list(all_leads.filter(last_contacted_at__isnull=False).only("created_at", "last_contacted_at"))
    if responded_leads:
        average_response_seconds = sum(
            max((lead.last_contacted_at - lead.created_at).total_seconds(), 0) for lead in responded_leads
        ) / len(responded_leads)
        average_response = f"{average_response_seconds / 3600:.1f} hrs" if average_response_seconds < 86400 else f"{average_response_seconds / 86400:.1f} days"
    else:
        average_response = "—"
    open_pipeline_value = all_leads.exclude(
        status__in=[Lead.Status.BOOKED, Lead.Status.LOST]
    ).pipeline_value()

    overdue_retainers = open_invoices.filter(due_date__lt=timezone.localdate()).count()
    awaiting_replies = all_leads.filter(status=Lead.Status.NEW).count()
    upcoming_session_count = sessions.filter(
        starts_at__lt=now + timedelta(days=7), status=ClientSession.Status.CONFIRMED,
    ).count()
    action_center = [
        {"count": awaiting_replies, "description": "new leads awaiting response", "icon": "bi-reply", "priority": "Urgent", "tone": "urgent", "related": "Newest unanswered leads", "action": "Reply now", "url": f"{reverse('photographer_workspace:leads')}?status={Lead.Status.NEW}"},
        {"count": 4, "description": "contracts awaiting signature", "icon": "bi-pen", "priority": "Due Soon", "tone": "soon", "related": "Client contracts requiring follow-up", "action": "Review booking contract", "url": contract_workspace_url},
        {"count": open_invoices.count(), "description": "outstanding payments", "icon": "bi-credit-card-2-front", "priority": "Urgent" if overdue_retainers else "Due Soon", "tone": "urgent" if overdue_retainers else "soon", "related": "Open client invoices", "action": "Review payments", "url": reverse("photographer_workspace:payments")},
        {"count": 2, "description": "questionnaires awaiting completion", "icon": "bi-ui-checks-grid", "priority": "Follow Up", "tone": "followup", "related": "Client preparation forms", "action": "View forms", "url": reverse("photographer_workspace:clients")},
        {"count": upcoming_session_count, "description": f"upcoming session{'s' if upcoming_session_count != 1 else ''} this week", "icon": "bi-calendar-event", "priority": "Upcoming", "tone": "followup", "related": "Confirmed sessions in the next 7 days", "action": "Open schedule", "url": reverse("photographer_workspace:calendar")},
    ]
    action_center = [item for item in action_center if item["count"]]
    priority_rank = {"urgent": 0, "soon": 1, "followup": 2}
    action_center.sort(key=lambda item: (priority_rank[item["tone"]], -item["count"]))

    context = _dashboard_context(request, "bookings", "Overview")
    context.update({
        "booking_state": request.GET.get("state") if request.GET.get("state") in {"loading", "error"} else "ready",
        "range_key": range_key,
        "range_label": range_options[range_key],
        "range_options": range_options.items(),
        "booking_metrics": [
            {"label": "Upcoming Bookings", "value": sessions.count(), "icon": "bi-calendar2-check", "support": range_options[range_key], "indicator": "Schedule", "tone": "neutral", "tooltip": "Non-cancelled sessions scheduled within the selected date range.", "link_label": "View bookings", "url": reverse("photographer_workspace:calendar")},
            {"label": "New Inquiries", "value": new_inquiries, "icon": "bi-chat-left-text", "support": "Awaiting first response", "indicator": "Needs review" if new_inquiries else "All caught up", "tone": "warning" if new_inquiries else "positive", "tooltip": "Active inquiries that have not yet moved beyond the new stage.", "link_label": "Review inquiries", "url": reverse("photographer_workspace:leads")},
            {"label": "Pending Contracts", "value": 4, "icon": "bi-file-earmark-text", "support": "Awaiting signature", "indicator": "Sample data", "tone": "neutral", "tooltip": "Placeholder count of contracts awaiting a client signature; contract data will replace this sample when connected.", "link_label": "Review booking", "url": contract_workspace_url},
            {"label": "Outstanding Payments", "value": f"{profile.default_currency} {outstanding:,.2f}", "icon": "bi-credit-card", "support": f"Across {open_invoices.count()} open invoice{'s' if open_invoices.count() != 1 else ''}", "indicator": "Action needed" if outstanding else "Up to date", "tone": "warning" if outstanding else "positive", "tooltip": "Remaining balance on invoices that are neither paid nor void.", "link_label": "Review payments", "url": reverse("photographer_workspace:payments")},
            {"label": "Booking Revenue", "value": f"{profile.default_currency} {paid_revenue:,.2f}", "icon": "bi-graph-up-arrow", "support": "Payments collected", "indicator": "All time", "tone": "positive", "tooltip": "Total payments recorded against your client invoices.", "link_label": "View revenue", "url": reverse("photographer_workspace:revenue")},
            {"label": "Conversion Rate", "value": f"{conversion_rate:.0f}%", "icon": "bi-funnel", "support": "Inquiries booked", "indicator": f"{all_leads.filter(status=Lead.Status.BOOKED).count()} converted", "tone": "positive" if conversion_rate else "neutral", "tooltip": "Percentage of active inquiries whose current status is booked.", "link_label": "View pipeline", "url": reverse("photographer_workspace:leads")},
        ],
        "upcoming_bookings": sessions.filter(status=ClientSession.Status.CONFIRMED).order_by("starts_at")[:5],
        "today_sessions": today_sessions[:5],
        "today_focus": [
            {"icon": "bi-camera", "value": today_sessions.count(), "label": "shoots today"},
            {"icon": "bi-pen", "value": 1, "label": "contract awaiting signature"},
            {"icon": "bi-cash-stack", "value": f"{profile.default_currency} {outstanding:,.0f}", "label": "payment due"},
            {"icon": "bi-images", "value": 1, "label": "gallery ready for delivery"},
        ],
        "schedule_owner": profile.display_name or request.user.full_name or "Studio team",
        "recent_inquiries": inquiries.order_by("-created_at")[:5],
        "inquiry_pipeline": inquiry_pipeline,
        "pipeline_inquiry_count": all_leads.count(),
        "pipeline_insights": [
            {"label": "Inquiry-to-booking conversion", "value": f"{conversion_rate:.0f}%", "icon": "bi-funnel"},
            {"label": "Average response time", "value": average_response, "icon": "bi-clock-history"},
            {"label": "Estimated open-pipeline value", "value": f"{profile.default_currency} {open_pipeline_value:,.2f}", "icon": "bi-cash-stack"},
        ],
        "action_center": action_center,
        "action_count": sum(item["count"] for item in action_center),
        "revenue_summary": {
            "booked": monthly_booked, "collected": monthly_collected,
            "outstanding": monthly_booked - monthly_collected, "average": monthly_average,
            "change": period_change,
        },
        "revenue_chart": revenue_chart,
        "revenue_chart_points": " ".join(f'{point["x"]},{point["y"]}' for point in revenue_chart),
        "session_breakdown": session_breakdown,
        "recent_booking_activity": recent_activity,
        "booking_quick_actions": [
            {"label": "New Lead", "icon": "bi-envelope-plus", "url": reverse("photographer_workspace:add_lead"), "help": "Capture a new lead"},
            {"label": "New Booking", "icon": "bi-calendar-plus", "url": f'{reverse("photographer_workspace:bookings")}?action=new', "help": "Start a client booking"},
            {"label": "Block Time", "icon": "bi-calendar-x", "url": f'{reverse("photographer_workspace:calendar")}?action=block', "help": "Reserve unavailable time"},
            {"label": "Share Booking Link", "icon": "bi-link-45deg", "url": f'{reverse("photographer_workspace:bookings")}?action=share', "help": "Copy your public booking link"},
        ],
    })
    return render(request, "photographer_workspace/bookings/dashboard.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def booking_detail(request, pk):
    """Keep booking-specific documents within the booking workspace."""
    profile = request.user.photographer_profile
    booking = get_object_or_404(
        ClientSession.objects.select_related("client"), photographer=profile, pk=pk,
    )
    if request.method == "POST" and request.POST.get("action") in {"send_contract", "send_contract_reminder"}:
        action = "Contract reminder" if request.POST["action"] == "send_contract_reminder" else "Contract"
        messages.success(request, f"{action} queued for {booking.client}.")
        return redirect(f'{reverse("photographer_workspace:booking_detail", args=[booking.pk])}?tab=contract#contract')

    tab = request.GET.get("tab", "overview")
    if tab not in {"overview", "contract"}:
        tab = "overview"
    context = _dashboard_context(request, "bookings", f"Booking LP-{booking.pk:04d}")
    context.update({
        "booking": booking,
        "booking_tab": tab,
        # Contract records are intentionally not duplicated here. The booking owns
        # the document workflow; this presentation remains ready for the existing
        # contract service to supply its status, signatures, and signed PDF.
        "contract_status": "Awaiting signature",
        "contract_is_signed": False,
    })
    return render(request, "photographer_workspace/bookings/detail.html", context)


@photographer_workspace_required
@require_GET
def schedule(request):
    """Render the responsive schedule with booking data and an illustrative empty state."""
    profile = request.user.photographer_profile
    today = timezone.localdate()
    try:
        selected_date = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        selected_date = today

    view = request.GET.get("view", "month")
    view_labels = {"month": "Month", "week": "Week", "day": "Day", "agenda": "Agenda", "list": "Booking List"}
    if view not in view_labels:
        view = "month"

    month_start = selected_date.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    previous_month = (month_start - timedelta(days=1)).replace(day=1)
    week_start = selected_date - timedelta(days=selected_date.weekday())
    if view == "month":
        range_start, range_end = month_start, next_month
        previous_date, next_date = previous_month, next_month
        date_range_label = selected_date.strftime("%B %Y")
    elif view == "week":
        range_start, range_end = week_start, week_start + timedelta(days=7)
        previous_date, next_date = selected_date - timedelta(days=7), selected_date + timedelta(days=7)
        date_range_label = f'{week_start.strftime("%b %-d")} – {(range_end - timedelta(days=1)).strftime("%b %-d, %Y")}'
    elif view == "day":
        range_start, range_end = selected_date, selected_date + timedelta(days=1)
        previous_date, next_date = selected_date - timedelta(days=1), selected_date + timedelta(days=1)
        date_range_label = selected_date.strftime("%A, %B %-d, %Y")
    else:
        range_start, range_end = selected_date, selected_date + timedelta(days=30)
        previous_date, next_date = selected_date - timedelta(days=30), selected_date + timedelta(days=30)
        date_range_label = f'{selected_date.strftime("%b %-d")} – {(range_end - timedelta(days=1)).strftime("%b %-d, %Y")}'

    filter_values = {
        "q": request.GET.get("q", "").strip(),
        "member": request.GET.get("member", ""),
        "session_type": request.GET.get("session_type", ""),
        "status": request.GET.get("status", ""),
        "event_type": request.GET.get("event_type", ""),
        "location": request.GET.get("location", ""),
        "scope": request.GET.get("scope", "studio"),
        "availability": request.GET.get("availability", ""),
        "show_completed": request.GET.get("show_completed", ""),
        "show_cancelled": request.GET.get("show_cancelled", ""),
    }
    filter_query = urlencode([(key, value) for key, value in filter_values.items() if value])
    sessions_queryset = ClientSession.objects.filter(
        photographer=profile,
        starts_at__date__gte=range_start,
        starts_at__date__lt=range_end,
    )
    visible_statuses = [ClientSession.Status.TENTATIVE, ClientSession.Status.CONFIRMED]
    if filter_values["show_completed"]:
        visible_statuses.append(ClientSession.Status.COMPLETED)
    if filter_values["show_cancelled"]:
        visible_statuses.append(ClientSession.Status.CANCELLED)
    if filter_values["status"]:
        visible_statuses = [filter_values["status"]]
    sessions_queryset = sessions_queryset.filter(status__in=visible_statuses)
    if filter_values["q"]:
        term = filter_values["q"]
        booking_number = term.upper().removeprefix("LP-").removeprefix("#")
        query = (Q(client__first_name__icontains=term) | Q(client__last_name__icontains=term) |
                 Q(session_type__icontains=term) | Q(location__icontains=term))
        if booking_number.isdigit():
            query |= Q(pk=int(booking_number))
        sessions_queryset = sessions_queryset.filter(query)
    if filter_values["session_type"]:
        sessions_queryset = sessions_queryset.filter(session_type=filter_values["session_type"])
    if filter_values["location"]:
        sessions_queryset = sessions_queryset.filter(location=filter_values["location"])
    if filter_values["event_type"] and filter_values["event_type"] != "booking":
        sessions_queryset = sessions_queryset.none()
    all_profile_sessions = ClientSession.objects.filter(photographer=profile)
    session_types = list(all_profile_sessions.exclude(session_type="").values_list("session_type", flat=True).distinct().order_by("session_type"))
    locations = list(all_profile_sessions.exclude(location="").values_list("location", flat=True).distinct().order_by("location"))
    sessions = list(sessions_queryset.select_related("client").order_by("starts_at"))
    owner = request.user.full_name or "Studio photographer"
    events = [{
        "id": session.pk,
        "starts_at": timezone.localtime(session.starts_at),
        "ends_at": timezone.localtime(session.starts_at) + timedelta(minutes=session.duration_minutes),
        "name": str(session.client), "session_type": session.session_type,
        "booking_number": f"LP-{session.pk:04d}", "location": session.location or "Location not set",
        "photographer": owner, "status": session.get_status_display(),
        "kind": "booking", "icon": "bi-camera", "warning": session.status == ClientSession.Status.TENTATIVE,
        "persisted": True, "move_url": reverse("photographer_workspace:reschedule_session", args=[session.pk]),
        "all_day": False, "url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
        "contact": " · ".join(value for value in (session.client.email, session.client.phone) if value) or "No contact information",
        "contact_email": session.client.email,
        "package": "Package not assigned", "contract_status": "Not signed",
        "payment_status": "Retainer unpaid", "questionnaire_status": "Incomplete",
        "notes": "No internal notes have been added.",
        "warnings": ["Contract not signed", "Retainer unpaid", "Questionnaire incomplete"] if session.status == ClientSession.Status.TENTATIVE else [],
    } for session in sessions]

    # Until schedule-specific event models are connected, keep an empty calendar useful
    # with clearly disclosed, realistic sample work. Existing bookings always take priority.
    using_sample_events = not events
    if using_sample_events:
        anchor = selected_date if view == "day" else (today if (selected_date.year, selected_date.month) == (today.year, today.month) else week_start)
        samples = [
            (0, 9, "Harper family", "Family portraits", "booking", "Confirmed", "bi-camera", False, False, 2),
            (0, 10, "Maya & Theo", "Wedding consultation", "consultation", "Tentative", "bi-chat-square-text", True, False, 1),
            (1, 13, "Rivera wedding", "Upcoming shoot", "booking", "Confirmed", "bi-camera", True, False, 3),
            (2, 9, "Nora Chen", "Brand mini session", "mini", "6 slots open", "bi-people", False, False, 4),
            (3, 8, "Miller gallery", "Editing day", "editing", "In progress", "bi-magic", False, True, 8),
            (4, 12, "Studio maintenance", "Blocked time", "blocked", "Unavailable", "bi-slash-circle", False, False, 3),
            (5, 0, "Summer break", "Vacation", "vacation", "Away", "bi-sun", False, True, 24),
            (1, 10, "Olivia Bennett", "Newborn session", "booking", "Tentative", "bi-camera", True, False, 2),
        ]
        events = []
        for offset, hour, name, session_type, kind, status, icon, warning, all_day, duration in samples:
            event_date = anchor + timedelta(days=offset)
            starts_at = timezone.make_aware(datetime.combine(event_date, time(hour=hour)))
            events.append({
                "id": 1000 + offset,
                "starts_at": starts_at, "ends_at": starts_at + timedelta(hours=duration),
                "name": name, "session_type": session_type, "photographer": owner,
                "booking_number": f"LP-{1000 + offset:04d}", "location": "LumisPixel Studio" if kind != "vacation" else "Away",
                "status": status, "kind": kind, "icon": icon, "warning": warning,
                "persisted": False, "move_url": "",
                "all_day": all_day, "url": reverse("photographer_workspace:bookings"),
                "contact": "hello@example.com · (555) 014-2086", "package": "Signature Collection",
                "contact_email": "hello@example.com",
                "contract_status": "Signed" if not warning else "Not signed",
                "payment_status": "Paid" if not warning else "Retainer unpaid",
                "questionnaire_status": "Complete" if not warning else "Incomplete",
                "notes": "Confirm arrival instructions with the client before the event.",
                "warnings": (["Contract not signed", "Retainer unpaid", "Questionnaire incomplete"] if kind == "booking" and warning else
                             ["Scheduling conflict"] if kind == "consultation" and warning else
                             ["Travel time may be insufficient"] if kind == "mini" else []),
            })

    action_labels = {
        "booking": ["Open Full Booking", "Contact Client", "Edit Booking", "Reschedule", "Mark Complete", "Create Gallery", "Cancel Booking"],
        "consultation": ["Contact Client", "Edit Consultation", "Reschedule", "Convert to Booking", "Cancel Consultation"],
        "editing": ["Open Gallery", "Edit Time", "Reschedule", "Mark Complete"],
        "blocked": ["Edit Block", "Reschedule", "Remove Block"],
        "vacation": ["Edit Vacation", "Change Dates", "Remove Vacation"],
        "mini": ["Manage Mini Session", "View Registrations", "Edit Session", "Reschedule", "Contact Attendees", "Cancel Session"],
    }
    for index, event in enumerate(events):
        event["drawer_id"] = f"schedule-event-{index}"
        event["duration"] = str(event["ends_at"] - event["starts_at"]).removeprefix("0:")
        event["actions"] = action_labels[event["kind"]]

    # Apply the same normalized filter state to illustrative and persisted events so
    # switching calendar modes never changes the result set.
    if using_sample_events:
        q = filter_values["q"].casefold()
        def sample_matches(event):
            searchable = " ".join(str(event.get(key, "")) for key in ("name", "booking_number", "session_type", "location")).casefold()
            return (
                (not q or q in searchable) and
                (not filter_values["member"] or filter_values["member"] == "me") and
                (not filter_values["session_type"] or event["session_type"] == filter_values["session_type"]) and
                (not filter_values["status"] or event["status"].casefold().replace(" ", "_") == filter_values["status"]) and
                (not filter_values["event_type"] or event["kind"] == filter_values["event_type"]) and
                (not filter_values["location"] or event["location"] == filter_values["location"]) and
                (filter_values["show_completed"] or event["status"] != "Completed") and
                (filter_values["show_cancelled"] or event["status"] != "Cancelled")
            )
        events = [event for event in events if sample_matches(event)]
        session_types = sorted({event["session_type"] for event in events} | {item[3] for item in samples})
        locations = ["Away", "LumisPixel Studio"]

    # Keep the schedule's operational summary intentionally narrow: what is next
    # today, the next confirmed shoots, and only issues that need intervention.
    now = timezone.localtime()
    todays_schedule = sorted(
        (event for event in events if event["starts_at"].date() == today and event["ends_at"] >= now),
        key=lambda event: event["starts_at"],
    )[:5]
    if todays_schedule:
        todays_schedule[0]["is_next"] = True

    upcoming_shoots = sorted(
        (
            event for event in events
            if event["kind"] in ("booking", "mini")
            and event["status"].casefold() == "confirmed"
            and event["starts_at"] >= now
        ),
        key=lambda event: event["starts_at"],
    )[:5]
    for event in upcoming_shoots:
        event["preparation_incomplete"] = any((
            event["contract_status"] != "Signed",
            event["payment_status"] != "Paid",
            event["questionnaire_status"] != "Complete",
            event["location"] in ("", "Location not set"),
            not event["photographer"],
        ))

    alert_icons = {
        "Scheduling conflict": "bi-calendar2-x",
        "Travel time may be insufficient": "bi-car-front",
        "Contract not signed": "bi-file-earmark-x",
        "Retainer unpaid": "bi-credit-card",
        "Questionnaire incomplete": "bi-clipboard-x",
    }
    scheduling_alerts = []
    for event in events:
        for warning in event["warnings"]:
            if len(scheduling_alerts) == 5:
                break
            scheduling_alerts.append({
                "title": warning,
                "event": event["name"],
                "when": event["starts_at"],
                "icon": alert_icons.get(warning, "bi-exclamation-triangle"),
                "drawer_id": event["drawer_id"],
            })

    events_by_date = {}
    for event in events:
        events_by_date.setdefault(event["starts_at"].date(), []).append(event)

    agenda_groups = []
    for event_date in sorted(events_by_date):
        if event_date == today:
            relative_label = "Today"
        elif event_date == today + timedelta(days=1):
            relative_label = "Tomorrow"
        else:
            relative_label = "Upcoming"
        agenda_groups.append({
            "date": event_date,
            "relative_label": relative_label,
            "events": events_by_date[event_date],
        })

    sort = request.GET.get("sort", "date")
    sort_options = {
        "date": lambda event: event["starts_at"],
        "date_desc": lambda event: event["starts_at"],
        "client": lambda event: event["name"].casefold(),
        "status": lambda event: event["status"].casefold(),
        "booking": lambda event: event["booking_number"],
    }
    if sort not in sort_options:
        sort = "date"
    booking_events = [event for event in events if event["kind"] == "booking" and event["status"].casefold() in ("confirmed", "tentative")]
    booking_events.sort(key=sort_options[sort], reverse=sort == "date_desc")
    booking_page = Paginator(booking_events, 10).get_page(request.GET.get("page", 1))
    list_query_values = [(key, value) for key, value in filter_values.items() if value]
    list_query_values.extend((("view", "list"), ("date", selected_date.isoformat()), ("sort", sort)))
    list_query = urlencode(list_query_values)

    calendar_weeks = []
    for week in Calendar(firstweekday=0).monthdatescalendar(selected_date.year, selected_date.month):
        calendar_weeks.append([
            {
                "date": day,
                "in_month": day.month == selected_date.month,
                "is_today": day == today,
                "events": events_by_date.get(day, []),
            }
            for day in week
        ])

    context = _dashboard_context(request, "calendar", "Schedule")
    context.update({
        "schedule_view": view,
        "schedule_view_label": view_labels[view],
        "schedule_views": view_labels.items(),
        "selected_date": selected_date,
        "today": today,
        "date_range_label": date_range_label,
        "previous_date": previous_date,
        "next_date": next_date,
        "calendar_weeks": calendar_weeks,
        "schedule_events": events,
        "using_sample_events": using_sample_events,
        "week_days": [{"date": range_start + timedelta(days=offset), "events": events_by_date.get(range_start + timedelta(days=offset), [])} for offset in range((range_end - range_start).days)],
        "agenda_groups": agenda_groups,
        "booking_page": booking_page,
        "booking_sort": sort,
        "list_query": list_query,
        "filter_values": filter_values,
        "session_type_options": session_types,
        "location_options": locations,
        "event_type_options": [("booking", "Bookings"), ("consultation", "Consultations"), ("editing", "Editing"), ("blocked", "Blocked Time"), ("vacation", "Vacation"), ("mini", "Mini Sessions")],
        "event_form_types": [("booking", "Booking", "bi-camera"), ("consultation", "Consultation", "bi-chat-square-text"), ("editing", "Editing Time", "bi-magic"), ("blocked", "Blocked Time", "bi-slash-circle"), ("vacation", "Vacation", "bi-sun"), ("mini", "Mini Session", "bi-people")],
        "booking_status_options": [("tentative", "Tentative"), ("confirmed", "Confirmed"), ("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled")],
        "active_filter_count": sum(bool(value) for key, value in filter_values.items() if key not in ("scope",)) + (filter_values["scope"] == "me"),
        "filter_query": filter_query,
        "todays_schedule": todays_schedule,
        "upcoming_shoots": upcoming_shoots,
        "scheduling_alerts": scheduling_alerts,
        "schedule_state": request.GET.get("state") if request.GET.get("state") in {"loading", "error"} else "ready",
    })
    return render(request, "photographer_workspace/bookings/schedule.html", context)


@photographer_workspace_required
@require_POST
def reschedule_session(request, pk):
    """Validate and atomically move one studio-owned booking."""
    import json

    profile = request.user.photographer_profile
    session = get_object_or_404(ClientSession, pk=pk, photographer=profile)
    try:
        payload = json.loads(request.body or "{}")
        starts_at = datetime.fromisoformat(payload["starts_at"].replace("Z", "+00:00"))
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at)
        duration = int(payload.get("duration_minutes", session.duration_minutes))
        if duration < 30 or duration > 1440 or duration % 15:
            raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Enter a valid start time and a duration in 15-minute increments."}, status=400)

    local_start = timezone.localtime(starts_at)
    end = starts_at + timedelta(minutes=duration)
    conflicts, travel_warning = [], False
    for other in ClientSession.objects.filter(photographer=profile).exclude(pk=session.pk).exclude(status=ClientSession.Status.CANCELLED):
        other_end = other.starts_at + timedelta(minutes=other.duration_minutes)
        if other.starts_at < end + timedelta(minutes=30) and other_end + timedelta(minutes=30) > starts_at:
            conflicts.append(f"{other.client} · {timezone.localtime(other.starts_at).strftime('%b %-d, %-I:%M %p')}")
            travel_warning = travel_warning or bool(session.location and other.location and session.location != other.location)
    available = local_start.weekday() < 5 and 9 <= local_start.hour < 17
    checks = [
        {"key": "conflict", "label": "Booking conflicts", "ok": not conflicts, "detail": "No overlapping bookings" if not conflicts else ", ".join(conflicts)},
        {"key": "availability", "label": "Photographer availability", "ok": available, "detail": "Within default working hours" if available else "Outside default Monday–Friday, 9 AM–5 PM availability"},
        {"key": "blocked", "label": "Blocked time & vacation", "ok": True, "detail": "No persisted blocked period applies"},
        {"key": "buffer", "label": "30-minute buffer", "ok": not conflicts, "detail": "Buffer is clear" if not conflicts else "Required buffer overlaps another booking"},
        {"key": "travel", "label": "Travel time", "ok": not travel_warning, "detail": "No travel issue detected" if not travel_warning else "Different locations may not leave enough travel time"},
    ]
    blocking = bool(conflicts)
    response = {"starts_at": local_start.isoformat(), "ends_at": timezone.localtime(end).isoformat(), "checks": checks,
                "blocking": blocking, "notify_recommended": session.status == ClientSession.Status.CONFIRMED}
    if payload.get("preview", True):
        return JsonResponse(response)
    if blocking:
        return JsonResponse(response | {"error": "Resolve booking and buffer conflicts before saving."}, status=409)
    with transaction.atomic():
        locked = ClientSession.objects.select_for_update().get(pk=session.pk, photographer=profile)
        locked.starts_at, locked.duration_minutes = starts_at, duration
        locked.save(update_fields=("starts_at", "duration_minutes"))
    return JsonResponse(response | {"saved": True, "notified": bool(payload.get("notify_client"))})


@photographer_workspace_required
@require_GET
def analytics_overview(request):
    """Render owner-scoped analytics directly from operational records."""
    context = _dashboard_context(request, "analytics", "Analytics")
    context.update(build_analytics_overview(request.user.photographer_profile, request.GET, request.path))
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="lumispixel-analytics.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(("LumisPixel analytics report", context["start"], context["end"]))
        writer.writerow(("Metric", "Selected period", "Comparison", "Change", "Definition", "Source workspace"))
        for metric in context["analytics_metrics"]:
            writer.writerow((metric["label"], metric["value"], metric["previous_value"], metric["change"], metric["tooltip"], metric["url"]))
        return response
    context["analytics_state"] = request.GET.get("state") if request.GET.get("state") in {"loading", "error", "permission", "empty"} else "ready"
    return render(request, "photographer_workspace/analytics/overview.html", context)


@photographer_workspace_required
@require_GET
def financial_overview(request):
    """Render date-scoped financial metrics from the reporting selector."""
    range_options = [
        ("this_month", "This month"),
        ("last_month", "Last month"),
        ("this_quarter", "This quarter"),
        ("this_year", "This year"),
        ("all_time", "All time"),
    ]
    range_key = request.GET.get("range", "this_month")
    if range_key not in {value for value, _ in range_options}:
        range_key = "this_month"
    page_state = request.GET.get("state", "empty")
    if page_state not in {"loading", "empty", "error"}:
        page_state = "empty"
    context = _dashboard_context(request, "financial_overview", "Financial Overview")
    profile = request.user.photographer_profile
    summary = financial_summary(profile, range_key, getattr(profile, "default_currency", "USD"))
    analytics = financial_analytics(profile, range_key, getattr(profile, "default_currency", "USD"))
    operations_state = request.GET.get("operations_state", "ready")
    if operations_state not in {"ready", "loading", "error"}:
        operations_state = "ready"
    operations = financial_operations(profile, getattr(profile, "default_currency", "USD"))
    activity_type = request.GET.get("activity_type", "")
    if activity_type not in TYPE_MAP:
        activity_type = ""
    activity_state = request.GET.get("activity_state", "ready")
    if activity_state not in {"ready", "loading", "error", "permission"}:
        activity_state = "ready"
    activity = financial_activity(profile, range_key, request.GET.get("page", 1), activity_type,
                                  getattr(profile, "default_currency", "USD"))
    context.update({"financial_state": page_state, "range_key": range_key, "range_options": range_options,
                    "financial_metrics": summary["cards"], "financial_has_activity": summary["has_activity"],
                    "financial_analytics": analytics, "financial_operations": operations,
                    "financial_operations_state": operations_state, "financial_activity": activity,
                    "financial_activity_state": activity_state})
    return render(request, "photographer_workspace/financial/overview.html", context)


@photographer_workspace_required
@require_GET
def growth_overview(request):
    """Render the responsive Growth workspace shell and its page-level states."""
    range_options = [
        ("last_30_days", "Last 30 days"),
        ("last_90_days", "Last 90 days"),
        ("this_quarter", "This quarter"),
        ("this_year", "This year"),
        ("all_time", "All time"),
    ]
    range_key = request.GET.get("range", "last_30_days")
    if range_key not in {value for value, _ in range_options}:
        range_key = "last_30_days"
    page_state = request.GET.get("state", "ready")
    if page_state not in {"ready", "loading", "empty", "permission", "error"}:
        page_state = "ready"
    context = _dashboard_context(request, "growth", "Growth Overview")
    metrics = growth_summary(request.user.photographer_profile, range_key,
                             getattr(request.user.photographer_profile, "default_currency", "USD"))
    for card in metrics["cards"]:
        card["url"] = f'{card["url"]}?range={range_key}'
    source_sort = request.GET.get("source_sort", "leads")
    currency = getattr(request.user.photographer_profile, "default_currency", "USD")
    source_metric = request.GET.get("source_metric", "booking_value")
    show_all_sources = request.GET.get("show_all_sources") == "1"
    section_states = {}
    for section in ("reviews", "referrals", "retention"):
        state = request.GET.get(f"{section}_state", "ready")
        section_states[section] = state if state in {"ready", "loading", "empty", "error", "permission"} else "ready"
    context.update({
        "growth_state": page_state,
        "range_key": range_key,
        "range_options": range_options,
        "compare_previous": request.GET.get("compare") == "1",
        "growth_metrics": metrics["cards"],
        "funnel_stages": [stage | {"url": f'{stage["url"]}&range={range_key}'}
                          for stage in lead_funnel(request.user.photographer_profile, range_key, currency)],
        "source_rows": lead_source_performance(request.user.photographer_profile, range_key, currency, source_sort),
        "source_sort": source_sort,
        "source_chart": booking_value_by_source(request.user.photographer_profile, range_key, source_metric,
                                                 show_all_sources, currency),
        "show_all_sources": show_all_sources,
        "service_rows": service_performance(request.user.photographer_profile, range_key, currency),
        "section_states": section_states,
        "reviews": reputation_summary(request.user.photographer_profile, range_key),
        "referrals": referral_summary(request.user.photographer_profile, range_key, currency),
        "retention": retention_summary(request.user.photographer_profile, range_key, currency),
        "opportunities": growth_opportunities(request.user.photographer_profile,
                                                request.GET.get("show_all_opportunities") == "1"),
        "recent_growth_activity": recent_growth_activity(request.user.photographer_profile),
        "recent_campaigns": GrowthCampaign.objects.for_photographer(request.user.photographer_profile)[:5],
    })
    return render(request, "photographer_workspace/growth/overview.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def growth_action(request):
    """Create deliberately small, studio-scoped growth records."""
    profile = request.user.photographer_profile
    action = request.GET.get("action") or request.POST.get("action")
    allowed = {"reviews", "referral", "import", "campaign"}
    if action not in allowed:
        return redirect("photographer_workspace:growth")
    completed_bookings = (ClientSession.objects.for_photographer(profile)
                          .filter(status=ClientSession.Status.COMPLETED)
                          .select_related("client").order_by("-starts_at"))
    if request.method == "POST":
        if action == "reviews":
            booking_ids = {value for value in request.POST.getlist("bookings") if value.isdigit()}
            bookings = completed_bookings.filter(pk__in=booking_ids)
            created = 0
            with transaction.atomic():
                for booking in bookings:
                    review_request, was_created = ReviewRequest.objects.get_or_create(
                        photographer=profile, booking=booking,
                        defaults={"client": booking.client, "message": request.POST.get("message", "")[:500],
                                  "status": ReviewRequest.Status.SENT, "sent_at": timezone.now()})
                    if was_created:
                        created += 1
                        ClientActivity.objects.create(
                            photographer=profile, client=booking.client,
                            event_type=ClientActivity.EventType.EMAIL_SENT,
                            description="Review request sent.",
                            metadata={"growth_event": "review_request", "review_request_id": review_request.pk,
                                      "booking_id": booking.pk})
            if not booking_ids:
                messages.error(request, "Select at least one completed booking.")
            elif not created:
                messages.info(request, "Those bookings already have review requests; no duplicates were sent.")
            else:
                messages.success(request, f"Created {created} review request{'s' if created != 1 else ''}.")
                return redirect(f'{reverse("photographer_workspace:growth")}?range={request.POST.get("range", "last_30_days")}#reviews')
        elif action == "referral":
            referral_type = request.POST.get("referral_type")
            if referral_type not in ReferralLink.ReferralType.values:
                messages.error(request, "Select a valid referral type.")
            else:
                client = Client.objects.for_photographer(profile).filter(pk=request.POST.get("client")).first()
                campaign = GrowthCampaign.objects.for_photographer(profile).filter(pk=request.POST.get("campaign")).first()
                code = secrets.token_urlsafe(9).replace("_", "").replace("-", "")
                link = ReferralLink.objects.create(
                    photographer=profile, label=request.POST.get("label", "Referral link")[:150], code=code,
                    referral_type=referral_type, referrer_name=request.POST.get("referrer_name", "")[:150],
                    client=client, campaign=campaign, status=request.POST.get("status")
                    if request.POST.get("status") in ReferralLink.Status.values else ReferralLink.Status.ACTIVE)
                messages.success(request, "Referral link created. Copy it from the referrals section.")
                return redirect(f'{reverse("photographer_workspace:growth")}?range={request.POST.get("range", "last_30_days")}#referrals')
        elif action == "campaign":
            name = request.POST.get("name", "").strip()
            if not name:
                messages.error(request, "Campaign name is required.")
            else:
                GrowthCampaign.objects.create(
                    photographer=profile, name=name[:150], campaign_type=request.POST.get("campaign_type", "")[:80],
                    status=request.POST.get("status") if request.POST.get("status") in GrowthCampaign.Status.values else GrowthCampaign.Status.DRAFT,
                    start_date=request.POST.get("start_date") or None, end_date=request.POST.get("end_date") or None,
                    target_audience=request.POST.get("target_audience", "")[:200], channel=request.POST.get("channel", "")[:80],
                    tracking_link=request.POST.get("tracking_link", ""), spend=request.POST.get("spend") or None,
                    notes=request.POST.get("notes", ""))
                messages.success(request, "Campaign record created.")
                return redirect(f'{reverse("photographer_workspace:growth")}?range={request.POST.get("range", "last_30_days")}#campaigns')
        else:
            upload = request.FILES.get("file")
            if not upload:
                messages.error(request, "Choose a CSV file to import.")
            else:
                rows = csv.DictReader(io.StringIO(upload.read().decode("utf-8-sig")))
                leads = [Lead(photographer=profile, first_name=(row.get("first_name") or "").strip(),
                              last_name=(row.get("last_name") or "").strip(), email=(row.get("email") or "").strip(),
                              phone=(row.get("phone") or "").strip(), lead_source=(row.get("lead_source") or "Import").strip())
                         for row in rows if (row.get("first_name") or row.get("email"))]
                Lead.objects.bulk_create(leads, batch_size=500)
                messages.success(request, f"Imported {len(leads)} lead{'s' if len(leads) != 1 else ''}.")
                return redirect(f'{reverse("photographer_workspace:growth")}?range={request.POST.get("range", "last_30_days")}#lead-funnel')
    context = _dashboard_context(request, "growth", "Promote your business")
    context.update({"growth_action": action, "range_key": request.GET.get("range", "last_30_days"),
                    "eligible_bookings": completed_bookings.exclude(review_requests__isnull=False),
                    "clients": Client.objects.for_photographer(profile).order_by("first_name", "last_name"),
                    "campaigns": GrowthCampaign.objects.for_photographer(profile),
                    "referral_types": ReferralLink.ReferralType.choices, "referral_statuses": ReferralLink.Status.choices,
                    "campaign_statuses": GrowthCampaign.Status.choices})
    return render(request, "photographer_workspace/growth/action.html", context)


@photographer_workspace_required
@require_GET
def growth_export(request):
    """Export all date-scoped growth sections as a portable CSV report."""
    profile, range_key = request.user.photographer_profile, request.GET.get("range", "last_30_days")
    if range_key not in {"last_30_days", "last_90_days", "this_quarter", "this_year", "all_time"}:
        range_key = "last_30_days"
    currency = getattr(profile, "default_currency", "USD")
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["LumisPixel growth report", range_key]); writer.writerow([])
    writer.writerow(["Key metric", "Value"])
    for card in growth_summary(profile, range_key, currency)["cards"]:
        writer.writerow([card["title"], card["formatted_value"]])
    sections = [("Funnel stages", lead_funnel(profile, range_key, currency), ["label", "count", "overall_rate", "formatted_value"]),
                ("Source performance", lead_source_performance(profile, range_key, currency), ["source", "leads", "bookings", "conversion_rate", "formatted_booking_value"]),
                ("Service performance", service_performance(profile, range_key, currency), ["service", "leads", "bookings", "conversion_rate", "formatted_value"])]
    for title, rows, fields in sections:
        writer.writerow([]); writer.writerow([title]); writer.writerow(fields)
        for row in rows: writer.writerow([row.get(field, "") for field in fields])
    for title, data in (("Reviews", reputation_summary(profile, range_key)), ("Referrals", referral_summary(profile, range_key, currency)), ("Retention", retention_summary(profile, range_key, currency))):
        writer.writerow([]); writer.writerow([title]);
        for key, value in data.items():
            if not isinstance(value, (list, dict)): writer.writerow([key, value])
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="lumispixel-growth-{range_key}.csv"'
    return response


@photographer_workspace_required
@require_GET
def financial_transactions(request):
    """Render the unified, date-scoped financial transactions workspace shell."""
    range_options = [
        ("this_month", "This month"),
        ("last_month", "Last month"),
        ("this_quarter", "This quarter"),
        ("this_year", "This year"),
        ("all_time", "All time"),
    ]
    range_key = request.GET.get("range", "this_month")
    if range_key not in {value for value, _ in range_options}:
        range_key = "this_month"
    page_state = request.GET.get("state", "ready")
    if page_state not in {"ready", "loading", "empty", "permission", "error", "export_error", "action_error"}:
        page_state = "ready"

    view_options = [
        ("all", "All activity"), ("invoices", "Invoices"), ("payments", "Payments"),
        ("refunds", "Refunds"), ("credits", "Credits"), ("overdue", "Overdue"),
    ]
    view_key = request.GET.get("view", "all")
    if view_key not in {value for value, _ in view_options}:
        view_key = "all"
    filter_definitions = [
        ("q", "Search"), ("range", "Date"), ("status", "Status"), ("record_type", "Type"),
        ("client", "Client"), ("booking", "Booking"), ("payment_method", "Payment method"),
        ("amount_min", "Minimum"), ("amount_max", "Maximum"), ("currency", "Currency"),
        ("created_by", "Created by"), ("source", "Source"), ("due_from", "Due from"),
        ("due_to", "Due to"), ("paid_from", "Paid from"), ("paid_to", "Paid to"),
    ]
    selected_filters = {key: request.GET.get(key, "").strip() for key, _ in filter_definitions}
    # The default date window is useful context, but is not presented as an active filter.
    active_filters = []
    for key, label in filter_definitions:
        value = selected_filters[key]
        if not value or (key == "range" and value == "this_month"):
            continue
        query = request.GET.copy()
        query.pop(key, None)
        active_filters.append({"key": key, "label": label, "value": dict(range_options).get(value, value),
                               "remove_url": f"?{query.urlencode()}" if query else "?"})
    preserved_query = request.GET.copy()
    preserved_query.pop("view", None)
    views = []
    for value, label in view_options:
        query = preserved_query.copy()
        if value != "all":
            query["view"] = value
        views.append({"value": value, "label": label, "active": value == view_key,
                      "url": f"?{query.urlencode()}" if query else "?"})

    profile = request.user.photographer_profile
    currency = getattr(profile, "default_currency", "USD")
    summary = financial_summary(profile, range_key, currency)
    values = summary["values"]
    transaction_value = values["invoice_value"] + values["collected"] + values["refunds"] + values["credits"]
    summary_items = [
        {"label": "Total transaction value", "value": format_currency(transaction_value, currency), "icon": "bi-arrow-left-right"},
        {"label": "Payments collected", "value": format_currency(values["collected"], currency), "icon": "bi-cash-coin"},
        {"label": "Outstanding balance", "value": format_currency(values["outstanding"], currency), "icon": "bi-hourglass-split"},
        {"label": "Refund total", "value": format_currency(values["refunds"], currency), "icon": "bi-arrow-counterclockwise"},
    ]
    records = transaction_records(profile, selected_filters, view_key, request.GET.get("page", 1),
                                  request.GET.get("page_size", 25), request.GET.get("sort", "date"),
                                  request.GET.get("direction", "desc"), currency)
    if page_state == "ready" and not records["total"]:
        page_state = "empty"
    context = _dashboard_context(request, "transactions", "Transactions")
    clear_query = request.GET.copy()
    for key, _ in filter_definitions:
        clear_query.pop(key, None)
    sort_links = {}
    for key in ("date", "amount", "client", "reference", "status"):
        query = request.GET.copy()
        query["sort"] = key
        query["direction"] = "asc" if records["sort"] == key and records["direction"] == "desc" else "desc"
        query.pop("page", None)
        sort_links[key] = f"?{query.urlencode()}"
    page_query = request.GET.copy()
    page_query.pop("page", None)
    context.update({
        "range_key": range_key,
        "range_options": range_options,
        "transaction_state": page_state,
        "transaction_summary": summary_items,
        "transaction_has_activity": summary["has_activity"],
        "transaction_views": views,
        "transaction_view": view_key,
        "selected_filters": selected_filters,
        "active_filters": active_filters,
        "active_filter_count": len(active_filters),
        "clear_filters_url": f"?{clear_query.urlencode()}" if clear_query else "?",
        "transaction_records": records,
        "sort_links": sort_links,
        "page_query": page_query.urlencode(),
        "financial_clients": Client.objects.for_photographer(profile).filter(status=Client.Status.ACTIVE),
        "financial_invoices": ClientInvoice.objects.for_photographer(profile).select_related("client").exclude(status__in=[ClientInvoice.Status.DRAFT, ClientInvoice.Status.VOID, ClientInvoice.Status.PAID]),
        "refundable_payments": [
            {"payment": payment, "remaining": payment.amount - (payment.refunds.filter(status=PaymentRefund.Status.COMPLETED).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"))}
            for payment in InvoicePayment.objects.for_photographer(profile).filter(status=InvoicePayment.Status.COMPLETED).select_related("invoice__client")
        ],
        "payment_methods": InvoicePayment.Method.choices,
        "today": timezone.localdate(),
        "export_columns": EXPORT_COLUMNS,
    })
    return render(request, "photographer_workspace/financial/transactions.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def financial_transaction_export(request):
    """Export the current owner-scoped view or an explicit owner-scoped selection."""
    profile = request.user.photographer_profile
    filter_keys = ("q", "range", "status", "record_type", "client", "booking", "payment_method",
                   "amount_min", "amount_max", "currency", "created_by", "source", "due_from",
                   "due_to", "paid_from", "paid_to")
    filters = {key: request.GET.get(key, "").strip() for key in filter_keys}
    records = transaction_records(profile, filters, request.GET.get("view", "all"), 1, 25,
                                  request.GET.get("sort", "date"), request.GET.get("direction", "desc"),
                                  getattr(profile, "default_currency", "USD"), paginate=False)["rows"]
    try:
        selected = request.POST.getlist("records") if request.method == "POST" else []
        if selected:
            # Resolve first to enforce studio isolation even if an id is outside the current view.
            selected_objects(profile, selected)
            by_id = {row["id"]: row for row in transaction_records(
                profile, {"range": "all_time"}, "all", 1, 25, "date", "desc",
                getattr(profile, "default_currency", "USD"), paginate=False)["rows"]}
            records = [by_id[value] for value in selected if value in by_id]
        payload = csv_bytes(records, request.POST.getlist("columns") or request.GET.getlist("columns"))
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="lumispixel-financial-records.csv"'
    return response


@photographer_workspace_required
@require_POST
def financial_transaction_bulk(request):
    """Validate the complete selection before performing a bulk mutation or download."""
    values, action = request.POST.getlist("records"), request.POST.get("action", "")
    try:
        rows = selected_objects(request.user.photographer_profile, values)
        if action == "capabilities":
            return JsonResponse({"actions": available_actions(rows)})
        if action == "download":
            payload = invoice_zip(request.user.photographer_profile, values, lambda invoice:
                render_to_string("photographer_workspace/invoices/print.html", {"invoice": invoice}))
            response = HttpResponse(payload, content_type="application/zip")
            response["Content-Disposition"] = 'attachment; filename="lumispixel-invoices.zip"'
            return response
        count = run_bulk_action(request.user.photographer_profile, values, action, request.POST.get("note", ""))
        return JsonResponse({"ok": True, "count": count})
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)


def _action_errors(exc):
    if hasattr(exc, "message_dict"):
        return {key: values[0] for key, values in exc.message_dict.items()}
    return {"form": str(exc)}


@photographer_workspace_required
@require_POST
def financial_action(request, action):
    """Run a confirmed financial mutation and return refresh targets to the client."""
    handlers = {"payment": record_payment, "refund": issue_refund, "credit": add_credit}
    if action not in handlers:
        return JsonResponse({"error": "Unknown financial action."}, status=404)
    if request.POST.get("confirmed") != "yes":
        return JsonResponse({"errors": {"confirmation": "Confirm this financial action before continuing."}}, status=400)
    try:
        record, duplicate = handlers[action](request.user.photographer_profile, request.POST)
    except ValidationError as exc:
        return JsonResponse({"errors": _action_errors(exc)}, status=400)
    invoice = record.payment.invoice if isinstance(record, PaymentRefund) else record.invoice
    return JsonResponse({
        "ok": True, "duplicate": duplicate, "record_type": record.__class__.__name__, "record_id": record.pk,
        "invoice_id": invoice.pk, "detail_url": reverse("photographer_workspace:financial_record_detail", args=[action, record.pk]),
        "message": {"payment": "Payment recorded.", "refund": "Refund completed.", "credit": "Credit added."}[action],
    })


@photographer_workspace_required
@require_GET
def financial_record_detail_view(request, record_type, pk):
    """Return drawer markup for one owner-scoped financial record."""
    detail = financial_record_detail(request.user.photographer_profile, record_type, pk,
                                     getattr(request.user.photographer_profile, "default_currency", "USD"))
    if detail is None:
        return JsonResponse({"error": "This financial record was not found."}, status=404)
    html = render_to_string("photographer_workspace/financial/_record_detail.html", {"record": detail}, request=request)
    return JsonResponse({"html": html, "reference": detail["reference"]})


def _invoice_context(request, invoice=None, errors=None):
    profile = request.user.photographer_profile
    context = _dashboard_context(request, "invoices", "Create Invoice" if invoice is None else f"Invoice {invoice.invoice_number}")
    context.update({"invoice": invoice, "invoice_number": invoice.invoice_number if invoice else next_invoice_number(profile),
                    "clients": Client.objects.for_photographer(profile).filter(status=Client.Status.ACTIVE),
                    "bookings": ClientSession.objects.for_photographer(profile).exclude(status=ClientSession.Status.CANCELLED).select_related("client"),
                    "item_types": InvoiceLineItem.ItemType.choices,
                    "today": timezone.localdate(), "errors": errors or {}})
    return context


@photographer_workspace_required
@require_GET
def invoices_workspace(request):
    profile = request.user.photographer_profile
    invoices = ClientInvoice.objects.for_photographer(profile).select_related("client", "booking").prefetch_related("line_items")
    context = _dashboard_context(request, "invoices", "Invoices")
    context["invoices"] = invoices
    return render(request, "photographer_workspace/invoices/list.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def invoice_create(request):
    if request.method == "POST":
        try:
            invoice = save_invoice(request.user.photographer_profile, request.POST, send=request.POST.get("intent") == "send")
            messages.success(request, f"{invoice.invoice_number} was {'sent' if invoice.status == ClientInvoice.Status.SENT else 'saved as a draft'}.")
            return redirect("photographer_workspace:invoice_view", pk=invoice.pk)
        except ValidationError as exc:
            return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request, errors=exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}), status=400)
    return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request))


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def invoice_edit(request, pk):
    invoice = get_object_or_404(ClientInvoice.objects.for_photographer(request.user.photographer_profile).prefetch_related("line_items", "payment_schedule"), pk=pk)
    if invoice.status != ClientInvoice.Status.DRAFT:
        messages.error(request, "Only draft invoices can be edited.")
        return redirect("photographer_workspace:invoice_view", pk=pk)
    if request.method == "POST":
        try:
            invoice = save_invoice(request.user.photographer_profile, request.POST, invoice, request.POST.get("intent") == "send")
            messages.success(request, "Invoice updated.")
            return redirect("photographer_workspace:invoice_view", pk=pk)
        except ValidationError as exc:
            return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request, invoice, exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}), status=400)
    return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request, invoice))


@photographer_workspace_required
@require_GET
def invoice_view(request, pk):
    invoice = get_object_or_404(ClientInvoice.objects.for_photographer(request.user.photographer_profile).select_related("client", "booking").prefetch_related("line_items", "payment_schedule", "activity"), pk=pk)
    return render(request, "photographer_workspace/invoices/detail.html", _invoice_context(request, invoice))


@photographer_workspace_required
@require_POST
def invoice_action(request, pk, action):
    profile = request.user.photographer_profile
    with transaction.atomic():
        invoice = get_object_or_404(ClientInvoice.objects.select_for_update().filter(photographer=profile), pk=pk)
        if action == "duplicate":
            source = ClientInvoice.objects.prefetch_related("line_items", "payment_schedule").get(pk=invoice.pk)
            duplicate = ClientInvoice.objects.create(photographer=profile, client=source.client, booking=source.booking,
                invoice_number=next_invoice_number(profile), issue_date=timezone.localdate(), due_date=timezone.localdate() + timedelta(days=source.payment_terms),
                payment_terms=source.payment_terms, currency=source.currency, subtotal=source.subtotal, discount_total=source.discount_total,
                tax_total=source.tax_total, total=source.total, client_notes=source.client_notes, internal_notes=source.internal_notes, terms=source.terms)
            for item in source.line_items.all(): item.pk = None; item.invoice = duplicate; item.save()
            InvoiceActivity.objects.create(photographer=profile, invoice=duplicate, action="duplicated", description=f"Duplicated from {source.invoice_number}.")
            messages.success(request, "Draft duplicate created.")
            return redirect("photographer_workspace:invoice_edit", pk=duplicate.pk)
        if action in {"send", "resend"}:
            if invoice.status not in {ClientInvoice.Status.DRAFT, ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID} or not invoice.client.email:
                messages.error(request, "This invoice cannot be sent in its current state, or the client has no email address.")
            else:
                invoice.status, invoice.sent_at = ClientInvoice.Status.SENT if invoice.status == ClientInvoice.Status.DRAFT else invoice.status, timezone.now()
                invoice.save(update_fields=["status", "sent_at"])
                InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action=action, description="Invoice emailed to client.")
                messages.success(request, "Invoice sent.")
        elif action == "void":
            if invoice.status in {ClientInvoice.Status.PAID, ClientInvoice.Status.VOID} or invoice.amount_paid > 0:
                messages.error(request, "Paid, partially paid, or already void invoices cannot be voided.")
            else:
                invoice.status = ClientInvoice.Status.VOID; invoice.save(update_fields=["status"])
                InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="voided", description="Invoice voided.")
                messages.success(request, "Invoice voided.")
        elif action == "payment":
            if invoice.status in {ClientInvoice.Status.PAID, ClientInvoice.Status.VOID, ClientInvoice.Status.DRAFT}:
                messages.error(request, "A payment cannot be recorded for this invoice.")
            else:
                try: amount = Decimal(request.POST.get("amount", "0")).quantize(Decimal("0.01"))
                except Exception: amount = Decimal("0")
                if amount <= 0 or amount > invoice.balance:
                    messages.error(request, "Payment must be greater than zero and no more than the balance.")
                else:
                    InvoicePayment.objects.create(photographer=profile, invoice=invoice, amount=amount)
                    invoice.amount_paid += amount; invoice.status = ClientInvoice.Status.PAID if invoice.amount_paid == invoice.total else ClientInvoice.Status.PARTIALLY_PAID
                    invoice.save(update_fields=["amount_paid", "status"])
                    InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="payment", description=f"Payment of {amount} recorded.")
                    messages.success(request, "Payment recorded.")
    return redirect("photographer_workspace:invoice_view", pk=pk)


@photographer_workspace_required
@require_GET
def invoice_download(request, pk):
    invoice = get_object_or_404(ClientInvoice.objects.for_photographer(request.user.photographer_profile).select_related("client").prefetch_related("line_items"), pk=pk)
    html = render_to_string("photographer_workspace/invoices/print.html", {"invoice": invoice})
    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.html"'
    return response


@photographer_workspace_required
@require_GET
def module_placeholder(request, module_key):
    module = MODULE_BY_KEY[module_key]
    context = _dashboard_context(request, module_key, module["title"])
    context["module"] = module | {"url": _reverse_module(module)}
    return render(request, "photographer_workspace/placeholder.html", context)


TEAM_PAGES = {
    "team_overview": ("Overview", "Monitor team workload, availability, assignments, capacity, and recent activity.", "bi-grid-1x2"),
    "team_members": ("Members", "Manage team members, invitations, profiles, roles, permissions, locations, working hours, and time off.", "bi-person-badge"),
    "team_performance": ("Performance", "Review productivity, booking contribution, revenue contribution, turnaround times, client experience, workload trends, and team activity.", "bi-graph-up-arrow"),
}


@photographer_workspace_required
@require_GET
def team_placeholder(request, page_key):
    if page_key == "team_overview":
        return team_overview(request)
    if page_key == "team_members":
        return team_members(request)
    title, subtitle, icon = TEAM_PAGES[page_key]
    context = _dashboard_context(request, page_key, title)
    context["team_page"] = {"title": title, "subtitle": subtitle, "icon": icon}
    return render(request, "photographer_workspace/team/temporary_page.html", context)


def team_members(request):
    """Owner-scoped directory using the account/profile records available today."""
    profile = authorized_studio(request.user)
    query = (request.GET.get("q", "") or "").strip()[:150]
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")
    if role not in {"", "owner", "studio_manager", "photographer"}:
        role = ""
    if status not in {"", "active", "inactive"}:
        status = ""

    name = request.user.full_name or profile.display_name or request.user.email
    location = ", ".join(part for part in (profile.city, profile.state, profile.country) if part)
    owner = {
        "name": name,
        "email": request.user.email,
        "initials": "".join(part[0] for part in name.split()[:2]).upper() or "LP",
        "role": "Owner",
        "status": "Active" if request.user.can_login else "Inactive",
        "location": location or "Not configured",
        "availability": "Not configured",
        "last_active": request.user.last_login,
    }
    matches = (
        (not query or query.casefold() in f"{name} {request.user.email} {location}".casefold())
        and (not role or role == "owner")
        and (not status or status == owner["status"].casefold())
    )
    members = [owner] if matches else []
    context = _dashboard_context(request, "team_members", "Team Members")
    context.update({
        "members": members,
        "owner": owner,
        "query": query,
        "selected_role": role,
        "selected_status": status,
        "summary": {
            "active": 1 if request.user.can_login else 0,
            "managers": 0,
            "photographers": 0,
            "pending": 0,
            "inactive": 0 if request.user.can_login else 1,
        },
    })
    return render(request, "photographer_workspace/team/members.html", context)


def team_overview(request):
    """Owner-scoped team snapshot built only from records that exist today."""
    profile = authorized_studio(request.user)
    filters = parse_team_filters(request.GET)
    selected_date, selected_location = filters["date"], filters["location"]
    search_term, selected_role, selected_availability = filters["q"], filters["role"], filters["availability"]
    locations, day_sessions, upcoming, day_start, day_end = studio_sessions(profile, selected_date, selected_location)
    upcoming_end = day_end + timedelta(days=14)

    # ClientSession is the booking/schedule source of truth. Team-member assignment
    # records do not exist yet, so this overview deliberately reports that gap and
    # links back to the established booking workflow rather than inventing one.
    now = timezone.now()

    def overlaps(candidate, collection):
        return any(sessions_overlap(candidate, other) for other in collection)

    def assignment_row(session, collection, upcoming_row=False):
        ends_at = session.starts_at + timedelta(minutes=session.duration_minutes)
        conflict = overlaps(session, collection)
        missing_location = not bool(session.location.strip())
        if session.status == ClientSession.Status.COMPLETED:
            status, tone = "Completed", "success"
        elif conflict:
            status, tone = "Conflict", "danger"
        elif not upcoming_row and session.starts_at <= now < ends_at:
            status, tone = "In progress", "info"
        elif not upcoming_row and now >= ends_at:
            status, tone = "Delayed", "danger"
        else:
            status, tone = "Unassigned", "warning"
        issues = []
        if conflict:
            issues.append("Overlaps another booking")
        if missing_location:
            issues.append("Location missing")
        issues.append("Photographer not assigned")
        return {
            "session": session,
            "ends_at": ends_at,
            "status": status,
            "tone": tone,
            "assigned_names": [],
            "issue": " · ".join(issues),
            "needs_attention": conflict or missing_location or not session.status == ClientSession.Status.COMPLETED,
            "readiness": "Needs attention" if conflict or missing_location else "Assignment needed",
        }

    today_assignments = [assignment_row(session, day_sessions) for session in day_sessions]
    upcoming_assignments = [assignment_row(session, upcoming, True) for session in upcoming]
    upcoming_assignments.sort(key=lambda row: (not row["needs_attention"], row["session"].starts_at))

    # Only activity types that describe team operations belong in this feed.  The
    # application does not yet audit membership, assignments, availability, leave,
    # or role changes; ordinary CRM/gallery events must not be presented as team
    # activity. Gallery delivery is the sole compatible activity record today.
    activity = [
        {
            "title": item.get_event_type_display(),
            "description": item.description,
            "at": item.occurred_at,
            "icon": "bi-images",
        }
        for item in ClientActivity.objects.for_photographer(profile).filter(
            event_type=ClientActivity.EventType.GALLERY_DELIVERED
        )[:6]
    ]
    owner_name = request.user.full_name or profile.display_name or request.user.email
    initials = "".join(part[0] for part in owner_name.split()[:2]).upper() or "LP"
    confirmed = sum(session.status == ClientSession.Status.CONFIRMED for session in day_sessions)
    owner_location = ", ".join(part for part in (profile.city, profile.state, profile.country) if part) or "Location not configured"
    member_matches = (
        (not search_term or search_term.casefold() in owner_name.casefold())
        and (not selected_role or selected_role == "owner")
        and (not selected_location or selected_location == owner_location)
        and (not selected_availability or selected_availability == "not_configured")
    )
    workload_rows = [{
        "name": owner_name,
        "initials": initials,
        "role": "Owner",
        "assigned_shoots": None,
        "scheduled_hours": None,
        "available_hours": None,
        "utilization": None,
        "overlaps": None,
        "status": "Insufficient data",
        "tone": "neutral",
    }]

    alerts = []
    for row in today_assignments + upcoming_assignments:
        session = row["session"]
        timing = timezone.localtime(session.starts_at)
        if row["status"] == "Conflict":
            alerts.append({
                "severity": "High", "tone": "danger", "icon": "bi-calendar2-x",
                "title": "Scheduling conflict",
                "explanation": "This booking overlaps another shoot. No member assignment exists to resolve coverage.",
                "affected": f"{session.session_type} · {session.client}", "timing": timing,
                "action": "Review booking", "url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
            })
        if session.status != ClientSession.Status.COMPLETED:
            alerts.append({
                "severity": "Medium", "tone": "warning", "icon": "bi-person-exclamation",
                "title": "Unassigned upcoming shoot" if session.starts_at >= day_end else "Unassigned shoot",
                "explanation": "No photographer assignment is recorded for this booking.",
                "affected": f"{session.session_type} · {session.client}", "timing": timing,
                "action": "View booking", "url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
            })
    alerts.append({
        "severity": "Info", "tone": "neutral", "icon": "bi-clock-history",
        "title": "Missing availability",
        "explanation": "Working hours and time off are not configured, so capacity and leave conflicts cannot be calculated.",
        "affected": owner_name, "timing_label": "Selected day",
        "action": "View members", "url": reverse("photographer_workspace:team_members"),
    })
    kpis = [
        {"label": "Total active team members", "value": "1", "definition": "Active people with access to this studio workspace.", "status": "Current", "tone": "success", "icon": "bi-people", "available": True},
        {"label": "Available today", "value": "—", "definition": "Members inside configured working hours with remaining capacity.", "status": "Not configured", "tone": "neutral", "icon": "bi-person-check", "available": False},
        {"label": "On assignment", "value": "—", "definition": "Members linked to an active shoot on the selected date.", "status": "Data unavailable", "tone": "neutral", "icon": "bi-camera", "available": False},
        {"label": "Unavailable or on leave", "value": "—", "definition": "Members marked away, on leave, or outside working hours.", "status": "Not configured", "tone": "neutral", "icon": "bi-calendar-x", "available": False},
        {"label": "Unassigned shoots today", "value": str(len(day_sessions)), "definition": "Non-cancelled shoots without member-assignment records.", "status": "Needs review" if day_sessions else "Clear", "tone": "warning" if day_sessions else "success", "icon": "bi-exclamation-diamond", "available": True},
        {"label": "Team capacity utilization", "value": "—", "definition": "Assigned shoot time as a share of configured team working hours.", "status": "Data unavailable", "tone": "neutral", "icon": "bi-speedometer2", "available": False},
    ]

    context = _dashboard_context(request, "team_overview", "Team Overview")
    context.update({
        "selected_date": selected_date,
        "is_today": selected_date == timezone.localdate(),
        "selected_location": selected_location,
        "search_term": search_term,
        "selected_role": selected_role,
        "selected_availability": selected_availability,
        "display_state": "ready",
        "member_matches": member_matches,
        "owner_location": owner_location,
        "kpis": kpis,
        "locations": locations,
        "day_sessions": day_sessions,
        "today_assignments": today_assignments,
        "upcoming_sessions": upcoming,
        "upcoming_assignments": upcoming_assignments,
        "upcoming_end": upcoming_end.date(),
        "recent_activity": activity,
        "workload_rows": workload_rows,
        "team_alerts": alerts,
        "owner_name": owner_name,
        "owner_initials": initials,
        "confirmed_count": confirmed,
        "tentative_count": sum(session.status == ClientSession.Status.TENTATIVE for session in day_sessions),
        "capacity_percent": None,
        "total_hours": None,
        "last_updated": timezone.now(),
        "is_solo": True,
        "is_multi_location": len(locations) > 1,
    })
    return render(request, "photographer_workspace/team/overview.html", context)
