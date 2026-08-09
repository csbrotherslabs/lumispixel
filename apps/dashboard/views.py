from decimal import Decimal
from calendar import Calendar
from datetime import date, datetime, timedelta
import csv
import io
import mimetypes
import zipfile
import secrets
from urllib.parse import urlencode

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.db import DatabaseError, transaction
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Concat
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from PIL import Image, UnidentifiedImageError

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import (Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask,
                                InvoiceActivity, InvoiceCredit, InvoiceLineItem, InvoicePayment, Lead,
                                MiniSession, MiniSessionSlot, MiniSessionSlotBooking, PaymentRefund)
from apps.clients.forms import ClientTaskForm, CrmClientForm, LeadForm
from apps.clients.services import DuplicateClientError, convert_lead_to_client, create_client_note
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
from apps.dashboard.scheduling import availability_for, parse_local_datetime, studio_timezone
from apps.dashboard.dashboard_data import build_dashboard
from apps.dashboard.crm_overview import build_crm_overview
from apps.dashboard.models import (GrowthCampaign, ReferralLink, ReviewRequest, StudioInvitationEvent,
                                   ScheduleConstraint, StudioMembership, StudioMembershipEvent)
from apps.dashboard.access import ROLE_PERMISSIONS, ROLE_SUMMARIES as ACCESS_SUMMARIES, access_for, scope_assigned
from apps.dashboard.team_invitations import (INVITATION_RESEND_COOLDOWN, InvitationForm,
                                             ROLE_SUMMARIES, find_valid_invitation,
                                             issue_token, record, send_invitation)
from apps.dashboard.team_summary import authorized_studio, parse_team_filters, sessions_overlap, studio_sessions
from apps.dashboard.team_performance import (INSIGHT_RULES, _comparison_dates, build_member_insights,
                                             calculate_period_metrics, team_performance_report)

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
    try:
        access = access_for(user)
    except PermissionDenied:
        if user.primary_role == User.PrimaryRole.CLIENT:
            return redirect("clients:dashboard")
        return redirect("accounts:post-login-redirect")
    request.studio_access = access
    request.studio = access.studio
    # Booking wall times are entered and displayed in the studio's configured
    # zone while Django continues to persist aware datetimes in UTC.
    timezone.activate(studio_timezone(access.studio))
    if access.membership is None and not access.studio.onboarding_completed:
        return redirect("photographers:setup-dashboard")
    return None


def photographer_workspace_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        response = _photographer_workspace_response(request)
        if response:
            return response
        name = request.resolver_match.url_name if request.resolver_match else ""
        owner_only = {"billing", "financial_overview", "transactions", "invoices", "invoice_create",
                      "invoice_view", "invoice_edit", "invoice_download", "invoice_action", "growth",
                      "settings", "revenue", "payments"}
        team_pages = {"team_overview", "team_members", "team_member_detail", "invite_member",
                      "invitation_action", "team_performance", "team_performance_member"}
        if name in owner_only and not request.studio_access.allows("financials" if name not in {"growth"} else "growth"):
            raise PermissionDenied
        if name in team_pages and not request.studio_access.allows("team"):
            raise PermissionDenied
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
    profile = request.studio
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
    context = _dashboard_context(request)
    try:
        context.update(build_dashboard(request.studio_access))
    except DatabaseError:
        # Contain aggregation outages and never expose exception details or
        # synthetic business values in the response.
        context.update({
            "dashboard_error": True,
            "day_summary": "Your workspace summary is temporarily unavailable.",
            "today": timezone.localdate(),
            "attention_items": [], "kpis": [], "schedule_items": [],
            "gallery_queue": [], "activity_items": [], "performance_chart": [],
            "can_view_financials": request.studio_access.allows("financials"),
            "storage_bytes": 0, "insight": None, "has_business_data": False,
        })
    context["quick_actions"] = [
        {"label": "Upload Photos", "icon": "bi-cloud-arrow-up", "url": reverse("photographer_workspace:galleries"), "emphasis": True},
        {"label": "Create Gallery", "icon": "bi-images", "url": reverse("photographer_workspace:create_gallery"), "emphasis": True},
        {"label": "Add Client", "icon": "bi-person-plus", "url": reverse("photographer_workspace:add_client")},
        {"label": "Create Booking", "icon": "bi-calendar-plus", "url": reverse("photographer_workspace:bookings")},
        *([{"label": "Send Invoice", "icon": "bi-send", "url": reverse("photographer_workspace:invoice_create")}]
          if request.studio_access.allows("financials") else []),
        {"label": "Block Time", "icon": "bi-calendar-x", "url": reverse("photographer_workspace:schedule")},
    ]
    return render(request, "photographer_workspace/dashboard.html", context)


@photographer_workspace_required
@require_GET
def clients_crm(request):
    context = _dashboard_context(request, "crm", "Client CRM")
    context.update(build_crm_overview(request.studio_access))
    return render(request, "photographer_workspace/clients_crm.html", context)


def _crm_form_page(request, form_class, title, success_message, activity_type=None):
    profile = request.studio
    model = form_class._meta.model
    kwargs = {"instance": model(photographer=profile)}
    if form_class is ClientTaskForm:
        kwargs["photographer"] = profile
    if form_class is CrmClientForm:
        kwargs["photographer"] = profile
    form = form_class(request.POST or None, request.FILES or None, **kwargs)
    is_add_lead = form_class is LeadForm and title == "Add Lead"
    is_add_client = form_class is CrmClientForm and title == "Add Client"
    if is_add_lead:
        for field_name, label in {
            "event_type": "Event Type",
            "event_date": "Event Date",
            "lead_source": "Lead Source",
            "estimated_value": "Estimated Value",
            "next_follow_up": "Next Follow Up",
        }.items():
            form.fields[field_name].label = label
        form.fields["notes"].widget.attrs["placeholder"] = (
            "Preferences, budget, follow-up context, or other useful details…"
        )
    if request.method == "POST" and form.is_valid():
        # Persist the record and its existing CRM activity as one operation. The
        # studio always comes from the authenticated access context, never POST.
        with transaction.atomic():
            record = form.save(commit=False)
            record.photographer = profile
            record.full_clean()
            record.save()
            if isinstance(form, CrmClientForm) and form.cleaned_data.get("notes"):
                create_client_note(
                    client=record,
                    content=form.cleaned_data["notes"],
                    actor=request.user,
                )
            if activity_type:
                ClientActivity.objects.create(
                    photographer=profile,
                    actor=request.user,
                    lead=record,
                    event_type=activity_type,
                    description=f"Lead {record} was created.",
                )
        messages.success(request, success_message)
        if is_add_lead:
            return redirect(_lead_destination(request))
        return redirect("photographer_workspace:crm")
    if is_add_lead:
        for field_name, field in form.fields.items():
            described_by = []
            if field.help_text:
                described_by.append(f"id_{field_name}-help")
            if field_name in form.errors:
                field.widget.attrs["aria-invalid"] = "true"
                described_by.append(f"id_{field_name}-error")
            if described_by:
                field.widget.attrs["aria-describedby"] = " ".join(described_by)
    context = _dashboard_context(request, "crm", title)
    context.update({
        "form": form,
        "form_title": title,
        "is_client_form": form_class is CrmClientForm,
        "is_lead_form": form_class is LeadForm,
        "is_add_lead": is_add_lead,
        "is_add_client": is_add_client,
        "hide_topbar_heading": is_add_lead or is_add_client,
        "form_next": (
            reverse("photographer_workspace:leads")
            if is_add_lead and (request.POST.get("next") or request.GET.get("next")) == reverse("photographer_workspace:leads")
            else ""
        ),
    })
    return render(request, "photographer_workspace/crm_form.html", context)


def _lead_destination(request):
    """Only allow redirects back to known workspace pages."""
    return "photographer_workspace:leads" if request.POST.get("next") == reverse("photographer_workspace:leads") else "photographer_workspace:crm"


def _log_lead(profile, lead, event_type, description, metadata=None, client=None, actor=None):
    return ClientActivity.objects.create(
        photographer=profile, lead=lead, client=client, event_type=event_type,
        description=description, metadata=metadata or {}, actor=actor,
    )


def _record_stage_change(profile, lead, previous_status, *, actor, event_type=None, metadata=None, client=None):
    """Record one auditable event for an actual persisted stage transition."""
    if previous_status == lead.status:
        return None
    old_label = Lead.Status(previous_status).label
    new_label = lead.get_status_display()
    details = {"from": previous_status, "to": lead.status}
    details.update(metadata or {})
    return _log_lead(
        profile,
        lead,
        event_type or ClientActivity.EventType.STAGE_CHANGED,
        f"Lead stage changed from {old_label} to {new_label}.",
        details,
        client=client,
        actor=actor,
    )


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def add_lead(request):
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    return _crm_form_page(request, LeadForm, "Add Lead", "Lead created.", ClientActivity.EventType.LEAD_CREATED)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_lead(request, pk):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    form = LeadForm(request.POST or None, instance=lead)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Re-read under a lock so a repeated/stale submission cannot produce
            # duplicate activity or overwrite a change committed just before it.
            current = get_object_or_404(
                Lead.objects.select_for_update().for_photographer(profile),
                pk=pk,
                archived_at__isnull=True,
            )
            original_values = {
                field: getattr(current, field) for field in LeadForm._meta.fields
            }
            locked_form = LeadForm(request.POST, instance=current)
            if not locked_form.is_valid():
                form = locked_form
            else:
                changed_fields = locked_form.changed_data
                changes = {
                    field: {
                        "old": str(original_values[field] or ""),
                        "new": str(locked_form.cleaned_data.get(field) or ""),
                    }
                    for field in changed_fields
                }
                updated = locked_form.save(commit=False)
                updated.photographer = profile
                updated.full_clean()
                if changes:
                    updated.save()
                    labels = [
                        locked_form.fields[field].label or field.replace("_", " ").title()
                        for field in changed_fields
                    ]
                    _log_lead(
                        profile,
                        updated,
                        ClientActivity.EventType.LEAD_UPDATED,
                        f"Lead {updated} was updated: {', '.join(labels)}.",
                        {"changes": changes},
                        actor=request.user,
                    )
                    if "status" in changed_fields:
                        if updated.status == Lead.Status.BOOKED:
                            convert_lead_to_client(lead=updated, actor=request.user)
                        else:
                            _record_stage_change(
                                profile, updated, original_values["status"], actor=request.user
                            )
                messages.success(request, "Lead updated successfully.")
                return redirect("photographer_workspace:leads")
    context = _dashboard_context(request, "leads", "Edit Lead")
    converted_client = Client.objects.for_photographer(profile).filter(converted_lead=lead).first()
    conversion_activity = ClientActivity.objects.for_photographer(profile).filter(
        lead=lead, event_type=ClientActivity.EventType.LEAD_CONVERTED
    ).select_related("actor").first()
    context.update({
        "form": form,
        "form_title": "Edit Lead",
        "is_lead_form": True,
        "editing_lead": lead,
        "converted_client": converted_client,
        "conversion_activity": conversion_activity,
    })
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
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    task = get_object_or_404(ClientTask.objects.for_photographer(request.studio), pk=pk)
    if task.client_id:
        get_object_or_404(
            scope_assigned(Client.objects.all(), request.studio_access), pk=task.client_id
        )
    task.status = ClientTask.Status.COMPLETED
    task.save(update_fields=["status", "updated_at"])
    messages.success(request, "Task marked complete.")
    return redirect("photographer_workspace:leads" if task.lead_id else "photographer_workspace:crm")


@photographer_workspace_required
@require_POST
def update_lead_status(request, pk):
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    lead = get_object_or_404(
        Lead.objects.for_photographer(request.studio), pk=pk, archived_at__isnull=True
    )
    status = request.POST.get("status")
    if status not in Lead.Status.values:
        messages.error(request, "Select a valid lead status.")
    elif status == Lead.Status.LOST:
        messages.error(request, "Use Mark lost so a loss reason can be recorded.")
    elif status == lead.status:
        messages.info(request, "Lead is already in that stage.")
    elif Client.objects.filter(converted_lead=lead).exists():
        messages.error(request, "A converted lead must remain booked.")
    elif status == Lead.Status.BOOKED:
        try:
            convert_lead_to_client(lead=lead, actor=request.user)
        except DuplicateClientError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, "Lead booked and converted to a client.")
    else:
        previous_status = lead.status
        lead.status = status
        if status != Lead.Status.LOST:
            lead.lost_reason = ""
        lead.save(update_fields=["status", "lost_reason", "updated_at"])
        _record_stage_change(request.studio, lead, previous_status, actor=request.user)
        messages.success(request, "Lead status updated.")
    destination = "photographer_workspace:leads" if request.POST.get("next") == reverse("photographer_workspace:leads") else "photographer_workspace:crm"
    return redirect(destination)


@photographer_workspace_required
@require_GET
def leads_workspace(request):
    """Render the photographer-scoped lead pipeline in board or list form."""
    profile = request.studio
    base = Lead.objects.for_photographer(profile).filter(archived_at__isnull=True)
    leads = base.select_related("converted_client").annotate(last_activity_at=Max("activities__occurred_at"))
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    source = request.GET.get("source", "").strip()
    event_type = request.GET.get("event_type", "").strip()
    follow_up = request.GET.get("follow_up", "").strip()
    created_from = request.GET.get("created_from", "").strip()
    created_to = request.GET.get("created_to", "").strip()
    terminal = request.GET.get("terminal", "recent").strip()
    today = timezone.localdate()
    if terminal != "all" and not status:
        cutoff = timezone.now() - timedelta(days=90)
        leads = leads.exclude(Q(status__in=[Lead.Status.BOOKED, Lead.Status.LOST]) & Q(updated_at__lt=cutoff))
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
    if follow_up == "overdue":
        leads = leads.filter(next_follow_up__lt=today).exclude(status__in=[Lead.Status.BOOKED, Lead.Status.LOST])
    elif follow_up == "today":
        leads = leads.filter(next_follow_up=today).exclude(status__in=[Lead.Status.BOOKED, Lead.Status.LOST])
    elif follow_up == "upcoming":
        leads = leads.filter(next_follow_up__gt=today).exclude(status__in=[Lead.Status.BOOKED, Lead.Status.LOST])
    elif follow_up == "unscheduled":
        leads = leads.filter(next_follow_up__isnull=True).exclude(status__in=[Lead.Status.BOOKED, Lead.Status.LOST])
    try:
        if created_from:
            leads = leads.filter(created_at__date__gte=date.fromisoformat(created_from))
        if created_to:
            leads = leads.filter(created_at__date__lte=date.fromisoformat(created_to))
    except ValueError:
        created_from = created_to = ""

    allowed_sorts = {
        "newest": "-created_at", "oldest": "created_at", "name": "first_name",
        "event_date": F("event_date").asc(nulls_last=True),
        "value_high": F("estimated_value").desc(nulls_last=True),
        "value_low": F("estimated_value").asc(nulls_last=True),
    }
    sort = request.GET.get("sort", "newest")
    leads = leads.order_by(allowed_sorts.get(sort, "-created_at"))
    all_leads = base
    booked = all_leads.filter(status=Lead.Status.BOOKED).count()
    total = all_leads.count()
    summary = [
        {"label": "New Leads", "value": all_leads.filter(status=Lead.Status.NEW).count(), "icon": "bi-person-plus", "note": "Awaiting first contact"},
        {"label": "Follow-ups Due", "value": all_leads.overdue_followups(today).count(), "icon": "bi-clock-history", "note": "Need your attention"},
        {"label": "Active Pipeline Value", "value": f"{profile.default_currency} {all_leads.exclude(status__in=[Lead.Status.BOOKED, Lead.Status.LOST]).pipeline_value():,.0f}", "icon": "bi-cash-stack", "note": "Estimated value of open leads"},
        {"label": "Lead-to-Booking Conversion", "value": f"{(booked / total * 100) if total else 0:.1f}%", "icon": "bi-graph-up-arrow", "note": f"{booked} of {total} unarchived leads booked" if total else "No leads to measure yet"},
    ]
    filtered_leads = list(leads)
    stage_records = {key: [] for key, _ in Lead.Status.choices}
    for lead in filtered_leads:
        stage_records[lead.status].append(lead)
    stages = []
    for key, label in Lead.Status.choices:
        records = stage_records[key]
        stages.append({"key": key, "label": label,
                       "leads": records, "count": len(records),
                       "value": sum((item.estimated_value or Decimal("0")) for item in records)})
    paginator = Paginator(leads, 10)
    page = paginator.get_page(request.GET.get("page"))
    retained = request.GET.copy()
    retained.pop("page", None)
    sources = Lead.objects.for_photographer(profile).exclude(lead_source="").values_list("lead_source", flat=True).distinct().order_by("lead_source")
    event_types = Lead.objects.for_photographer(profile).exclude(event_type="").values_list("event_type", flat=True).distinct().order_by("event_type")
    tasks_due = ClientTask.objects.filter(photographer=profile, lead__archived_at__isnull=True, status__in=[ClientTask.Status.OPEN, ClientTask.Status.IN_PROGRESS]).select_related("lead").order_by(F("due_date").asc(nulls_last=True), "-priority")[:6]
    recent_activity = ClientActivity.objects.filter(photographer=profile, lead__isnull=False).select_related("lead").order_by("-occurred_at")[:5]
    source_rows = list(all_leads.exclude(lead_source="").values("lead_source").annotate(
        count=Count("id"), booked=Count("id", filter=Q(status=Lead.Status.BOOKED)),
        pipeline_value=Coalesce(Sum("estimated_value", filter=~Q(status__in=[Lead.Status.BOOKED, Lead.Status.LOST])), Value(Decimal("0")), output_field=DecimalField())
    ).order_by("-booked", "-count")[:5])
    for row in source_rows:
        row["conversion"] = row["booked"] / row["count"] * 100 if row["count"] else 0
    context = _dashboard_context(request, "leads", "Leads")
    context.update({"lead_summary": summary, "lead_stages": stages, "lead_page": page,
                    "add_lead_url": f'{reverse("photographer_workspace:add_lead")}?{urlencode({"next": reverse("photographer_workspace:leads")})}',
                    "lead_sources": sources, "lead_query": query, "selected_status": status,
                    "selected_source": source, "selected_event_type": event_type, "event_types": event_types,
                    "selected_sort": sort, "today": today, "tasks_due": tasks_due,
                    "recent_activity": recent_activity, "source_rows": source_rows,
                    "lead_status_choices": Lead.Status.choices, "result_count": len(filtered_leads),
                    "selected_follow_up": follow_up, "created_from": created_from, "created_to": created_to,
                    "terminal": terminal, "retained_query": retained.urlencode(),
                    "has_filters": any([query, status, source, event_type, follow_up, created_from, created_to, terminal == "all"])})
    return render(request, "photographer_workspace/leads.html", context)


@photographer_workspace_required
@require_GET
def clients_workspace(request):
    """Render the searchable, photographer-scoped client directory."""
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    profile = request.studio
    now = timezone.now()
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=DecimalField(max_digits=12, decimal_places=2))
    upcoming = scope_assigned(ClientSession.objects.all(), request.studio_access).filter(
        client=OuterRef("pk"), starts_at__gte=now,
    ).exclude(status=ClientSession.Status.CANCELLED).order_by("starts_at")
    can_view_financials = request.studio_access.allows("financials")
    invoices = ClientInvoice.objects.filter(
        photographer=profile, client=OuterRef("pk"),
    ) if can_view_financials else ClientInvoice.objects.none()
    invoices = invoices.exclude(status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID]).values("client").annotate(
        due=Sum(balance)
    )
    activity = ClientActivity.objects.filter(
        photographer=profile, client=OuterRef("pk")
    ).order_by("-occurred_at")
    all_clients = scope_assigned(Client.objects.all(), request.studio_access)
    clients = all_clients.annotate(
        next_session_at=Subquery(upcoming.values("starts_at")[:1]),
        next_session_type=Subquery(upcoming.values("session_type")[:1]),
        outstanding_balance=Coalesce(Subquery(invoices.values("due")[:1]), Value(Decimal("0.00")), output_field=DecimalField()),
        last_activity_at=Subquery(activity.values("occurred_at")[:1]),
        last_activity_label=Subquery(activity.values("description")[:1]),
    )
    # Keep directory parameters bounded and allowlisted before they reach the
    # queryset.  The form advertises "name", which includes the persisted full
    # name rather than only either name component in isolation.
    query = request.GET.get("q", "").strip()[:200]
    status = request.GET.get("status", "").strip()
    client_type = request.GET.get("client_type", "").strip()
    tag = request.GET.get("tag", "").strip()[:50]
    has_session = request.GET.get("upcoming", "").strip()
    has_balance = request.GET.get("balance", "").strip()
    status = status if status in Client.Status.values else ""
    client_type = client_type if client_type in Client.ClientType.values else ""
    has_session = has_session if has_session in {"yes", "no"} else ""
    has_balance = has_balance if has_balance in {"yes", "no"} else ""
    if query:
        clients = clients.annotate(
            search_full_name=Concat("first_name", Value(" "), "last_name")
        ).filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) |
                 Q(search_full_name__icontains=query) | Q(email__icontains=query) |
                 Q(phone__icontains=query) | Q(company__icontains=query))
    if status:
        clients = clients.filter(status=status)
    if client_type:
        clients = clients.filter(client_type=client_type)
    tags = sorted({str(item) for values in all_clients.values_list("tags", flat=True)
                   for item in (values or [])}, key=str.casefold)
    canonical_tag = next((item for item in tags if item.casefold() == tag.casefold()), None) if tag else None
    if tag:
        if canonical_tag is None:
            clients = clients.none()
        else:
            # JSON containment is not portable to every supported test database.
            # Keep this scoped projection small (only id/tags) and never load a
            # global client collection into application memory.
            matching_ids = [client.pk for client in clients.only("pk", "tags")
                            if canonical_tag.casefold() in {str(item).casefold() for item in client.tags}]
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

    outstanding_total = (all_clients.outstanding_balances().aggregate(
        total=Coalesce(Sum("balance_due"), Value(Decimal("0.00")), output_field=DecimalField())
    )["total"] if can_view_financials else Decimal("0.00"))
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    summary = [
        {"label": "Total Clients", "value": all_clients.count(), "icon": "bi-people", "note": "All client relationships"},
        {"label": "Active Clients", "value": all_clients.active().count(), "icon": "bi-person-check", "note": "Currently active"},
        {"label": "New This Month", "value": all_clients.filter(created_at__gte=month_start).count(), "icon": "bi-person-plus", "note": "Added since the start of the month"},
    ]
    if can_view_financials:
        summary.append({"label": "Outstanding Balance", "value": f"{profile.default_currency} {outstanding_total:,.2f}", "icon": "bi-wallet2", "note": "Across open invoices"})
    paginator = Paginator(clients, 12)
    page = paginator.get_page(request.GET.get("page"))
    retained = request.GET.copy()
    for key, value in (("q", query), ("status", status), ("client_type", client_type),
                       ("tag", canonical_tag or tag), ("upcoming", has_session),
                       ("balance", has_balance)):
        if value:
            retained[key] = value
        else:
            retained.pop(key, None)
    retained.pop("page", None)
    context = _dashboard_context(request, "clients", "Clients")
    context.update({
        "client_summary": summary, "client_page": page, "client_query": query,
        "selected_status": status, "selected_client_type": client_type, "selected_tag": canonical_tag or tag,
        "selected_upcoming": has_session, "selected_balance": has_balance, "client_tags": tags,
        "client_status_choices": Client.Status.choices, "client_type_choices": Client.ClientType.choices,
        "retained_query": retained.urlencode(), "result_count": paginator.count,
        "has_filters": any([query, status, client_type, tag, has_session, has_balance]),
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
    storage_percent = min(round(storage_used / GALLERY_STORAGE_LIMIT * 100), 100)
    return [
        {"label": "Total Galleries", "value": galleries.count(), "icon": "bi-images", "note": "Across every workflow stage"},
        {"label": "Active Galleries", "value": galleries.exclude(status__in=[Gallery.Status.ARCHIVED, Gallery.Status.EXPIRED, Gallery.Status.DELIVERED]).count(), "icon": "bi-activity", "note": "Currently in your workflow"},
        {"label": "Ready to Deliver", "value": galleries.filter(status=Gallery.Status.READY).count(), "icon": "bi-send-check", "note": "Awaiting your delivery"},
        {"label": "Storage Used", "value": _format_storage(storage_used), "icon": "bi-device-ssd", "note": f"{_format_storage(storage_used)} of 100 GB", "percent": storage_percent},
    ]


@photographer_workspace_required
@require_GET
def galleries_dashboard(request):
    galleries = Gallery.objects.for_photographer(request.studio).select_related("client")
    now = timezone.now()
    storage_used = galleries.aggregate(total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField()))["total"]
    pipeline_counts = {row["status"]: row["count"] for row in galleries.values("status").annotate(count=Count("id"))}
    pipeline = [
        {"key": key, "label": label, "count": pipeline_counts.get(key, 0), "percent": round(pipeline_counts.get(key, 0) / max(galleries.count(), 1) * 100)}
        for key, label in Gallery.Status.choices
        if key not in {Gallery.Status.ARCHIVED, Gallery.Status.EXPIRED}
    ]
    activity_icons = {
        GalleryActivity.EventType.CLIENT_VIEWED: "bi-eye",
        GalleryActivity.EventType.CLIENT_FAVORITED: "bi-heart",
        GalleryActivity.EventType.PHOTO_DOWNLOADED: "bi-download",
        GalleryActivity.EventType.GALLERY_DOWNLOADED: "bi-download",
        GalleryActivity.EventType.GALLERY_SHARED: "bi-share",
    }
    client_activity = GalleryActivity.objects.for_photographer(request.studio).filter(
        actor_type=GalleryActivity.ActorType.CLIENT,
        event_type__in=activity_icons,
    ).select_related("gallery")[:6]
    activity = [{"icon": activity_icons[item.event_type], "action": item.title or item.get_event_type_display(),
                 "gallery": item.gallery.name, "time": item.created_at, "url": reverse("photographer_workspace:gallery_workspace", args=[item.gallery_id])}
                for item in client_activity]
    deadlines = []
    for gallery in galleries.filter(Q(expires_at__gte=now) | Q(event_date__gte=timezone.localdate())).order_by("expires_at", "event_date")[:6]:
        if gallery.expires_at:
            days = (gallery.expires_at.date() - timezone.localdate()).days
            deadlines.append({"gallery": gallery, "type": "Expires", "date": gallery.expires_at, "urgency": "Urgent" if days <= 3 else "Soon", "urgent": days <= 3})
        elif gallery.event_date:
            days = (gallery.event_date - timezone.localdate()).days
            deadlines.append({"gallery": gallery, "type": "Delivery target", "date": gallery.event_date, "urgency": "Urgent" if days <= 3 else "Upcoming", "urgent": days <= 3})
    attention = []
    failed_jobs = AIJob.objects.for_photographer(request.studio).filter(status=AIJob.Status.FAILED).count()
    if failed_jobs:
        attention.append({"icon": "bi-exclamation-triangle", "title": f"{failed_jobs} processing job{'s' if failed_jobs != 1 else ''} failed", "description": "Review the failure details and retry when ready.", "url": reverse("photographer_workspace:ai_processing"), "action": "Review failures", "tone": "danger"})
    ready_count = galleries.filter(status=Gallery.Status.READY).count()
    if ready_count:
        attention.append({"icon": "bi-send-check", "title": f"{ready_count} {'galleries are' if ready_count != 1 else 'gallery is'} ready to deliver", "description": "Open the gallery to complete client delivery.", "url": reverse("photographer_workspace:all_galleries") + "?status=ready", "action": "View ready", "tone": "warning"})
    if storage_used / GALLERY_STORAGE_LIMIT >= Decimal("0.8"):
        attention.append({"icon": "bi-device-ssd", "title": "Storage is approaching its limit", "description": f"{_format_storage(storage_used)} of 100 GB is in use.", "url": reverse("photographer_workspace:gallery_upload_queue"), "action": "Manage storage", "tone": "warning"})
    recent_galleries = list(galleries[:6])
    for gallery in recent_galleries:
        gallery.delivery_label = "Delivered" if gallery.status == Gallery.Status.DELIVERED else "Published" if gallery.status == Gallery.Status.PUBLISHED else "Not delivered"
        gallery.badge_variant = "success" if gallery.status in {Gallery.Status.READY, Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED} else "warning" if gallery.status in {Gallery.Status.UPLOADING, Gallery.Status.PROCESSING, Gallery.Status.REVIEW} else "neutral"
    context = _dashboard_context(request, "galleries", "Galleries")
    context.update({
        "gallery_summary": _gallery_summary(galleries, storage_used), "recent_galleries": recent_galleries,
        "delivery_pipeline": pipeline, "recent_client_activity": activity, "gallery_attention": attention[:5],
        "storage": {"used": _format_storage(storage_used), "available": _format_storage(max(GALLERY_STORAGE_LIMIT - storage_used, 0)), "percent": min(round(storage_used / GALLERY_STORAGE_LIMIT * 100), 100), "percent_display": f"{min(round(storage_used / GALLERY_STORAGE_LIMIT * 100), 100)}%"},
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
    profile = request.studio
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
    job = get_object_or_404(AIJob.objects.for_photographer(request.studio), pk=pk)
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
    profile = request.studio
    card_photos = GalleryPhoto.objects.for_photographer(profile).filter(
        is_visible=True, status=GalleryPhoto.Status.COMPLETED
    ).order_by("-is_cover", "-created_at")
    all_records = Gallery.objects.for_photographer(profile).active().select_related("client").prefetch_related(
        Prefetch("photos", queryset=card_photos, to_attr="card_photos")
    )
    galleries = all_records
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    client = request.GET.get("client", "").strip()
    event_date = request.GET.get("event_date", "").strip()
    sort = request.GET.get("sort", "updated").strip()
    if query:
        galleries = galleries.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(client__first_name__icontains=query) | Q(client__last_name__icontains=query))
    if status in Gallery.Status.values:
        galleries = galleries.filter(status__in=[Gallery.Status.UPLOADING, Gallery.Status.PROCESSING]) if status == Gallery.Status.PROCESSING else galleries.filter(status=status)
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
    profile = request.studio
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
    profile = request.studio
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
    profile = request.studio
    form = GalleryForm(request.POST or None, request.FILES or None, photographer=profile)
    form.fields["description"].widget.attrs["rows"] = 3
    form.fields["cover_image"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
    form.fields["name"].widget.attrs["placeholder"] = "e.g. Maya & Rowan"
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
    if request.method == "POST":
        for field_name in form.errors:
            if field_name in form.fields:
                field = form.fields[field_name]
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"{field.widget.attrs.get('id', f'id_{field_name}')}-error"
    context = _dashboard_context(request, "all_galleries", "Create Gallery")
    context.update({"form": form, "form_title": "Create Gallery", "form_subtitle": "Set up the gallery now. Add photos and delivery settings next.", "submit_label": "Create Gallery", "is_create_gallery": True, "hide_topbar_heading": True})
    return render(request, "photographer_workspace/galleries/form.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_gallery(request, pk):
    profile = request.studio
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
    profile = request.studio
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
    profile = request.studio
    galleries = Gallery.objects.for_photographer(profile).select_related("client")
    if request.method == "POST":
        gallery = get_object_or_404(galleries, pk=request.POST.get("gallery"))
        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"error": "Choose at least one image."}, status=400)
        created, errors = [], []
        allowed = {"image/jpeg", "image/png", "image/webp"}
        max_size = 25 * 1024 * 1024
        storage_used = galleries.aggregate(
            total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField())
        )["total"]
        storage_remaining = max(GALLERY_STORAGE_LIMIT - storage_used, 0)
        for upload in files:
            if upload.content_type not in allowed or upload.size > max_size:
                errors.append({"name": upload.name, "error": "Use a JPG, PNG, or WebP image up to 25 MB."})
                continue
            if upload.size > storage_remaining:
                errors.append({"name": upload.name, "error": "Not enough storage to upload these files."})
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
            storage_remaining -= upload.size
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
    storage_percent = min(round(storage_used / GALLERY_STORAGE_LIMIT * 100), 100)
    selected_gallery = galleries.filter(pk=request.GET.get("gallery")).first() if request.GET.get("gallery") else None
    context = _dashboard_context(request, "gallery_upload_queue", "Upload Queue")
    context.update({"gallery_choices": galleries, "uploads": uploads, "upload_counts": counts,
                    "selected_gallery": selected_gallery,
                    "storage": {"used": _format_storage(storage_used),
                                "available": _format_storage(max(GALLERY_STORAGE_LIMIT - storage_used, 0)),
                                "available_bytes": max(GALLERY_STORAGE_LIMIT - storage_used, 0),
                                "percent": storage_percent}})
    return render(request, "photographer_workspace/galleries/upload_queue.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def gallery_workspace(request, pk):
    gallery = get_object_or_404(
        Gallery.objects.for_photographer(request.studio).select_related("client"), pk=pk
    )
    context = _dashboard_context(request, "all_galleries", gallery.name)
    tab = request.GET.get("tab", "overview")
    tabs = ("overview", "photos", "albums", "ai-tools", "client-access", "store", "downloads", "activity", "settings")
    if tab not in tabs:
        tab = "overview"
    permissions, _ = GalleryPermission.objects.get_or_create(gallery=gallery)
    settings, _ = GallerySettings.objects.get_or_create(gallery=gallery, defaults={"gallery_url": gallery.slug})
    store, _ = GalleryStore.objects.get_or_create(gallery=gallery, defaults={"photographer": request.studio, "name": f"{gallery.name} Store"})
    store_form = StoreSettingsForm(request.POST or None, instance=store, prefix="store")
    discount_form = DiscountCodeForm(request.POST or None, prefix="discount")
    settings_form = GallerySettingsForm(request.POST or None, request.FILES or None, instance=settings,
                                        photographer=request.studio, prefix="settings")
    general_form = GalleryForm(request.POST or None, request.FILES or None, instance=gallery,
                               photographer=request.studio, prefix="general")
    general_form.fields["status"].choices = [(value, label) for value, label in Gallery.Status.choices
                                               if value in {Gallery.Status.DRAFT, Gallery.Status.PUBLISHED, Gallery.Status.ARCHIVED}]
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_store":
            if store_form.is_valid():
                configured = store_form.save(commit=False); configured.photographer = request.studio; configured.gallery = gallery
                configured.full_clean(); configured.save(); messages.success(request, "Store settings saved.")
            else: messages.error(request, "Review the highlighted store settings.")
            tab = "store"
        elif action == "add_discount":
            if discount_form.is_valid():
                discount = discount_form.save(commit=False); discount.photographer = request.studio; discount.gallery = gallery
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
                    updated_gallery.slug = _unique_gallery_slug(request.studio, updated_gallery.name, gallery.pk)
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
                    duplicate.slug = _unique_gallery_slug(request.studio, duplicate.name)
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
    all_activity = GalleryActivity.objects.for_photographer(request.studio).filter(gallery=gallery)
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
    profile = request.studio
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
    profile = request.studio
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
    product = get_object_or_404(StoreProduct.objects.filter(photographer=request.studio), pk=pk)
    action = request.POST.get("action")
    if action == "delete": product.delete(); messages.success(request, "Product deleted.")
    elif action == "toggle": product.active=not product.active; product.save(update_fields=["active", "updated_at"])
    elif action == "duplicate":
        variants=list(product.variants.all()); product.pk=None; product.name += " Copy"; product.active=False; product.save()
        ProductVariant.objects.bulk_create([ProductVariant(product=product,name=v.name,price_adjustment=v.price_adjustment,display_order=v.display_order) for v in variants])
    return redirect(f"{reverse('photographer_workspace:gallery_workspace', args=[product.gallery_id])}?tab=store")


@photographer_workspace_required
def gallery_order_detail(request, pk):
    order = get_object_or_404(GalleryOrder.objects.filter(photographer=request.studio).select_related("gallery").prefetch_related("items__selected_photos"), pk=pk)
    context=_dashboard_context(request,"all_galleries",order.order_number); context["order"]=order
    return render(request,"photographer_workspace/galleries/order_detail.html",context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def create_album(request, gallery_pk):
    gallery = get_object_or_404(Gallery.objects.for_photographer(request.studio), pk=gallery_pk)
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
    album = get_object_or_404(Album.objects.for_photographer(request.studio).select_related("gallery"), pk=pk)
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
    album = get_object_or_404(Album.objects.for_photographer(request.studio).select_related("gallery", "cover_photo"), pk=pk)
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
    album = get_object_or_404(Album.objects.for_photographer(request.studio).select_related("gallery"), pk=pk)
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
    album = get_object_or_404(Album.objects.for_photographer(request.studio).select_related("gallery"), pk=pk)
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
    photo = get_object_or_404(GalleryPhoto.objects.for_photographer(request.studio), pk=pk)
    content_type = mimetypes.guess_type(photo.original_name)[0] or "application/octet-stream"
    response = FileResponse(photo.file.open("rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{photo.original_name.replace(chr(34), "")}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@photographer_workspace_required
@require_POST
def gallery_photo_action(request, pk):
    photo = get_object_or_404(GalleryPhoto.objects.for_photographer(request.studio).select_related("gallery"), pk=pk)
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
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    client = get_object_or_404(scope_assigned(Client.objects.all(), request.studio_access), pk=pk)
    form = CrmClientForm(
        request.POST or None,
        request.FILES or None,
        instance=client,
        photographer=profile,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            current = get_object_or_404(
                scope_assigned(Client.objects.select_for_update(), request.studio_access),
                pk=pk,
            )
            locked_form = CrmClientForm(
                request.POST,
                request.FILES or None,
                instance=current,
                photographer=profile,
            )
            if not locked_form.is_valid():
                form = locked_form
            else:
                changed_fields = list(locked_form.changed_data)
                notes = locked_form.cleaned_data.get("notes", "").strip()
                model_fields = set(CrmClientForm._meta.fields)
                changes = {
                    field: {
                        "old": str(locked_form.initial.get(field) or ""),
                        "new": str(locked_form.cleaned_data.get(field) or ""),
                    }
                    for field in changed_fields
                    if field in model_fields or field in {"tags_input", "lead_source", "city", "state_province", "postal_code", "country"}
                }
                updated = locked_form.save(commit=False)
                # Ownership and system-managed relationships always come from the
                # locked row/authenticated workspace, never submitted data.
                updated.photographer = current.photographer
                updated.full_clean()
                if changes:
                    updated.save()
                note_created = False
                if notes and not current.notes.filter(content=notes).exists():
                    create_client_note(client=updated, content=notes, actor=request.user)
                    note_created = True
                    changes["notes"] = {"old": "", "new": notes}
                if changes:
                    labels = [
                        locked_form.fields[field].label or field.replace("_", " ").title()
                        for field in changed_fields
                        if field in locked_form.fields and field != "notes"
                    ]
                    if note_created:
                        labels.append("Notes")
                    ClientActivity.objects.create(
                        photographer=profile,
                        client=updated,
                        actor=request.user,
                        event_type=ClientActivity.EventType.CLIENT_UPDATED,
                        description=f"Client {updated} was updated: {', '.join(labels)}.",
                        metadata={"changes": changes},
                    )
                messages.success(request, "Client updated successfully.")
                return redirect("photographer_workspace:client_detail", pk=updated.pk)
    context = _dashboard_context(request, "clients", "Edit Client")
    context.update({"form": form, "form_title": "Edit Client", "is_client_form": True})
    return render(request, "photographer_workspace/crm_form.html", context)


CLIENT_DETAIL_TABS = ("overview", "sessions", "galleries", "invoices", "activity")


@photographer_workspace_required
@require_GET
def client_detail(request, pk):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    client = get_object_or_404(scope_assigned(Client.objects.all(), request.studio_access), pk=pk)
    now, today = timezone.now(), timezone.localdate()
    sessions = scope_assigned(ClientSession.objects.all(), request.studio_access).filter(client=client)
    galleries = scope_assigned(Gallery.objects.all(), request.studio_access).filter(
        client=client, deleted_at__isnull=True
    )
    can_view_financials = request.studio_access.allows("financials")
    invoices = ClientInvoice.objects.for_photographer(profile).filter(client=client) if can_view_financials else ClientInvoice.objects.none()
    open_invoices = invoices.exclude(status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID])
    outstanding = sum((invoice.balance for invoice in open_invoices), Decimal("0.00"))
    upcoming = sessions.filter(starts_at__gte=now).exclude(status=ClientSession.Status.CANCELLED).first()
    overdue = open_invoices.filter(due_date__lt=today)
    soon = sessions.filter(starts_at__gte=now, starts_at__lte=now + timezone.timedelta(days=7)).exclude(status=ClientSession.Status.CANCELLED)
    detail_tabs = tuple(
        tab_name for tab_name in CLIENT_DETAIL_TABS
        if tab_name != "invoices" or can_view_financials
    )
    tab = request.GET.get("tab", "overview")
    if tab not in detail_tabs:
        tab = "overview"
    notes = ClientNote.objects.for_photographer(profile).filter(client=client).select_related("author")
    activities = ClientActivity.objects.for_photographer(profile).filter(client=client).select_related("actor")
    context = _dashboard_context(request, "clients", str(client))
    context.update({
        "client_record": client, "detail_tabs": detail_tabs, "active_tab": tab,
        "sessions": sessions, "galleries": galleries, "invoices": invoices, "upcoming_session": upcoming,
        "outstanding_balance": outstanding, "recent_notes": notes[:5],
        "client_tasks": client.tasks.exclude(status__in=[ClientTask.Status.COMPLETED, ClientTask.Status.CANCELLED]),
        "activities": activities[:30],
        "can_view_financials": can_view_financials,
        "operational_alerts": ([
            {"label": "Overdue invoices", "count": overdue.count(), "icon": "bi-receipt", "urgent": overdue.exists()},
        ] if can_view_financials else []) + [
            {"label": "Sessions in 7 days", "count": soon.count(), "icon": "bi-calendar-event", "urgent": soon.exists()},
            {"label": "Galleries awaiting delivery", "count": galleries.filter(status=Gallery.Status.READY).count(), "icon": "bi-images", "urgent": galleries.filter(status=Gallery.Status.READY).exists()},
        ],
    })
    return render(request, "photographer_workspace/client_detail.html", context)


@photographer_workspace_required
@require_POST
def client_archive_restore(request, pk):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    action = request.POST.get("action")
    if action not in {"archive", "restore"}:
        return HttpResponseBadRequest("Choose archive or restore.")

    # The client status is the existing retention boundary: related business
    # records remain attached. Locking plus an explicit desired state makes a
    # retried/double-submitted request idempotent rather than toggling it back.
    with transaction.atomic():
        client = get_object_or_404(
            scope_assigned(Client.objects.select_for_update(), request.studio_access),
            pk=pk,
        )
        target_status = Client.Status.ARCHIVED if action == "archive" else Client.Status.ACTIVE
        if client.status == target_status:
            verb = "already archived" if action == "archive" else "already active"
            messages.info(request, f"Client is {verb}.")
            return redirect("photographer_workspace:client_detail", pk=client.pk)

        client.status = target_status
        client.save(update_fields=["status", "updated_at"])
        event = (
            ClientActivity.EventType.CLIENT_ARCHIVED
            if action == "archive"
            else ClientActivity.EventType.CLIENT_RESTORED
        )
        verb = "archived" if action == "archive" else "restored"
        ClientActivity.objects.create(
            photographer=profile,
            client=client,
            actor=request.user,
            event_type=event,
            description=f"Client {client} was {verb}.",
        )
    messages.success(request, f"Client {verb}.")
    return redirect("photographer_workspace:client_detail", pk=client.pk)


@photographer_workspace_required
@require_POST
def add_client_note(request, pk):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    client = get_object_or_404(scope_assigned(Client.objects.all(), request.studio_access), pk=pk)
    content = request.POST.get("content", "").strip()
    if not content:
        messages.error(request, "Enter a note before saving.")
    elif len(content) > 5000:
        messages.error(request, "Notes must be 5,000 characters or fewer.")
    else:
        try:
            create_client_note(client=client, content=content, actor=request.user)
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Note added.")
    return redirect("photographer_workspace:client_detail", pk=client.pk)


@photographer_workspace_required
@require_POST
def add_client_task(request, pk):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    client = get_object_or_404(scope_assigned(Client.objects.all(), request.studio_access), pk=pk)
    data = request.POST.copy()
    data["client"] = client.pk
    data.pop("lead", None)
    form = ClientTaskForm(data, photographer=profile, instance=ClientTask(photographer=profile))
    if form.is_valid():
        task = form.save(commit=False)
        task.photographer = profile
        task.full_clean()
        task.save()
        ClientActivity.objects.create(photographer=profile, client=client, actor=request.user, event_type=ClientActivity.EventType.FOLLOW_UP_CREATED, description=f"Task created: {task.title}.")
        messages.success(request, "Task created.")
    else:
        messages.error(request, "Enter valid task details.")
    return redirect("photographer_workspace:client_detail", pk=client.pk)


@photographer_workspace_required
@require_POST
def bulk_update_leads(request):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    leads = Lead.objects.for_photographer(profile).filter(pk__in=request.POST.getlist("lead_ids"), archived_at__isnull=True)
    action = request.POST.get("action")
    if action in (Lead.Status.LOST, Lead.Status.BOOKED):
        messages.error(request, "Book or mark leads lost individually so the required client or loss details are recorded.")
    elif action in Lead.Status.values:
        updated = 0
        with transaction.atomic():
            for lead in leads.select_for_update():
                if hasattr(lead, "converted_client") and action != Lead.Status.BOOKED:
                    continue
                if lead.status == action:
                    continue
                previous_status = lead.status
                lead.status = action
                lead.save(update_fields=["status", "updated_at"])
                _record_stage_change(profile, lead, previous_status, actor=request.user)
                updated += 1
        messages.success(request, f"Updated {updated} lead{'s' if updated != 1 else ''}.")
    else:
        messages.error(request, "Choose a valid bulk action.")
    return redirect("photographer_workspace:leads")


@photographer_workspace_required
@require_POST
def archive_lead(request, pk):
    profile = request.studio
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    lead.archived_at = timezone.now()
    lead.save(update_fields=["archived_at", "updated_at"])
    _log_lead(profile, lead, ClientActivity.EventType.LEAD_ARCHIVED, f"Lead {lead} was archived.")
    messages.success(request, "Lead archived.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def create_lead_follow_up(request, pk):
    profile = request.studio
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
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    try:
        client, created = convert_lead_to_client(lead=lead, actor=request.user)
    except DuplicateClientError as error:
        messages.error(request, error.messages[0])
    else:
        if created:
            messages.success(request, "Lead booked and converted to a client.")
        else:
            messages.info(request, "This booked lead is already linked to a client.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def mark_lead_lost(request, pk):
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    lead = get_object_or_404(Lead.objects.for_photographer(profile), pk=pk, archived_at__isnull=True)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Provide a reason before marking this lead lost.")
    elif len(reason) > 255:
        messages.error(request, "Lost reason must be 255 characters or fewer.")
    elif lead.status == Lead.Status.LOST and lead.lost_reason == reason:
        messages.info(request, "This lead is already marked lost.")
    else:
        previous_status = lead.status
        lead.status, lead.lost_reason = Lead.Status.LOST, reason
        lead.save(update_fields=["status", "lost_reason", "updated_at"])
        _record_stage_change(
            profile, lead, previous_status, actor=request.user,
            event_type=ClientActivity.EventType.LEAD_LOST, metadata={"reason": reason},
        )
        messages.success(request, "Lead marked lost.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_POST
def add_lead_note(request, pk):
    profile = request.studio
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
    profile = request.studio
    if not request.studio_access.allows("clients"):
        raise PermissionDenied
    with transaction.atomic():
        lead = get_object_or_404(Lead.objects.select_for_update().for_photographer(profile), pk=pk)
        if Client.objects.filter(converted_lead=lead).exists():
            messages.error(request, "This lead has already been converted.")
            return redirect(_lead_destination(request))
        try:
            _client, created = convert_lead_to_client(lead=lead, actor=request.user)
        except DuplicateClientError as error:
            messages.error(request, error.messages[0])
            return redirect(_lead_destination(request))
        if not created:
            messages.error(request, "This lead has already been converted.")
            return redirect(_lead_destination(request))
    messages.success(request, "Lead converted to a client.")
    return redirect(_lead_destination(request))


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def bookings_dashboard(request):
    """Render the tenant-scoped booking operations overview."""
    profile = request.studio
    if request.method == "POST":
        if request.POST.get("action") in {"create_mini", "edit_mini"}:
            if not request.studio_access.allows("schedule"):
                raise PermissionDenied
            is_edit = request.POST["action"] == "edit_mini"
            mini_queryset = MiniSession.objects.for_photographer(profile)
            if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
                mini_queryset = mini_queryset.filter(assigned_members=request.studio_access.membership)
            mini = get_object_or_404(mini_queryset, pk=request.POST.get("mini_id")) if is_edit else None
            errors = {}
            name = request.POST.get("mini_name", "").strip()
            location = request.POST.get("mini_location", "").strip()
            if not name:
                errors["mini_name"] = "Enter a mini-session name."
            if not location:
                errors["mini_location"] = "Enter a location."
            try:
                starts_at = parse_local_datetime(profile, request.POST.get("start_date", ""), request.POST.get("start_time", ""))
                slot_duration = int(request.POST.get("slot_duration", "20"))
                slot_count = int(request.POST.get("slot_count", "6"))
                buffer_minutes = int(request.POST.get("buffer", "0"))
                capacity = int(request.POST.get("capacity", "1"))
                if min(slot_duration, slot_count, capacity) < 1 or buffer_minutes < 0 or slot_count > 100:
                    raise ValueError
            except (TypeError, ValueError):
                errors["slot_count"] = "Enter valid positive slot settings (up to 100 slots)."
            member_ids = {int(value) for value in request.POST.getlist("team") if value.isdigit()}
            valid_ids = set(StudioMembership.objects.filter(
                studio=profile, status=StudioMembership.Status.ACTIVE, pk__in=member_ids
            ).values_list("pk", flat=True))
            if valid_ids != member_ids:
                errors["team"] = "Select active photographers from this workspace."
            if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
                own_id = request.studio_access.membership.pk if request.studio_access.membership else None
                if member_ids != {own_id}:
                    raise PermissionDenied
            if errors:
                return JsonResponse({"ok": False, "errors": errors}, status=400)
            duration = slot_count * slot_duration + max(0, slot_count - 1) * buffer_minutes
            with transaction.atomic():
                PhotographerProfile.objects.select_for_update().get(pk=profile.pk)
                changing_grid = mini is None
                if mini:
                    mini = MiniSession.objects.select_for_update().get(pk=mini.pk, photographer=profile)
                    changing_grid = (mini.starts_at != starts_at or mini.slot_duration_minutes != slot_duration or
                                     mini.slot_count != slot_count or mini.buffer_minutes != buffer_minutes)
                    if changing_grid and mini.slots.filter(bookings__cancelled_at__isnull=True).exists():
                        return JsonResponse({"ok": False, "errors": {"start_time":
                            "Booked slots exist. Cancel or move those bookings before changing the slot grid."}}, status=409)
                    if mini.slots.annotate(active_count=Count(
                            "bookings", filter=Q(bookings__cancelled_at__isnull=True)
                        )).filter(active_count__gt=capacity).exists():
                        return JsonResponse({"ok": False, "errors": {"capacity":
                            "Capacity cannot be lower than an existing slot's active bookings."}}, status=409)
                available = availability_for(
                    studio=profile, starts_at=starts_at, duration_minutes=duration, member_ids=member_ids,
                    exclude_mini_pk=mini.pk if mini else None, lock=True,
                )
                if not available["available"]:
                    return JsonResponse({"ok": False, "errors": {"start_time": "This photographer is unavailable during the mini-session block."}}, status=409)
                values = {"name": name, "starts_at": starts_at, "slot_duration_minutes": slot_duration,
                          "slot_count": slot_count, "buffer_minutes": buffer_minutes,
                          "capacity_per_slot": capacity, "location": location,
                          "service": request.POST.get("mini_package", "").strip(),
                          "notes": request.POST.get("notes", "").strip()}
                if mini:
                    for field, value in values.items():
                        setattr(mini, field, value)
                    mini.save()
                else:
                    mini = MiniSession.objects.create(photographer=profile, **values)
                mini.assigned_members.set(member_ids)
                if changing_grid:
                    # Idempotent regeneration: only an unbooked changed grid is replaced.
                    mini.slots.all().delete()
                    step = slot_duration + buffer_minutes
                    MiniSessionSlot.objects.bulk_create([
                        MiniSessionSlot(mini_session=mini, position=index,
                                        starts_at=starts_at + timedelta(minutes=index * step),
                                        duration_minutes=slot_duration)
                        for index in range(slot_count)
                    ])
            return JsonResponse({"ok": True, "schedule_url": reverse("photographer_workspace:schedule")}, status=200 if is_edit else 201)
        if request.POST.get("action") in {"create_constraint", "edit_constraint"}:
            if not request.studio_access.allows("schedule"):
                raise PermissionDenied
            kind = request.POST.get("event_type")
            errors = {}
            if kind not in ScheduleConstraint.Kind.values:
                errors["event_type"] = "Choose a supported schedule event."
            title = request.POST.get("title", "").strip()
            reason = request.POST.get("reason", "").strip()
            if not title:
                errors["title"] = "Enter an event title."
            if kind in {ScheduleConstraint.Kind.BLOCKED, ScheduleConstraint.Kind.VACATION} and not reason:
                errors["reason"] = "Enter why this time is unavailable."
            all_day = request.POST.get("all_day") == "on"
            try:
                if all_day:
                    start_date = date.fromisoformat(request.POST.get("start_date", ""))
                    end_date = date.fromisoformat(request.POST.get("end_date", ""))
                    starts_at = parse_local_datetime(profile, start_date.isoformat(), "00:00")
                    ends_at = parse_local_datetime(profile, (end_date + timedelta(days=1)).isoformat(), "00:00")
                else:
                    starts_at = parse_local_datetime(profile, request.POST.get("start_date", ""), request.POST.get("start_time", ""))
                    ends_at = parse_local_datetime(profile, request.POST.get("end_date", ""), request.POST.get("end_time", ""))
                if ends_at <= starts_at:
                    errors["end_date"] = "The end must be after the start."
            except (TypeError, ValueError):
                starts_at = ends_at = None
                errors["start_date"] = "Enter a valid start and end date and time."
            member_ids = set()
            for raw_id in request.POST.getlist("team"):
                try:
                    member_ids.add(int(raw_id))
                except (TypeError, ValueError):
                    errors["team"] = "Select active photographers from this workspace."
            valid_ids = set(StudioMembership.objects.filter(
                studio=profile, status=StudioMembership.Status.ACTIVE, pk__in=member_ids,
            ).values_list("pk", flat=True))
            entire_team = request.POST.get("availability_scope") == "entire_team"
            if valid_ids != member_ids:
                errors["team"] = "Select active photographers from this workspace."
            if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
                own_id = request.studio_access.membership.pk if request.studio_access.membership else None
                if entire_team or member_ids != {own_id}:
                    raise PermissionDenied
            constraint = None
            if request.POST["action"] == "edit_constraint":
                constraint = get_object_or_404(ScheduleConstraint, studio=profile,
                                               pk=request.POST.get("constraint_id"))
                if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER and not constraint.assigned_members.filter(pk=request.studio_access.membership.pk).exists():
                    raise PermissionDenied
            if errors:
                return JsonResponse({"ok": False, "errors": errors}, status=400)
            values = {
                "kind": kind, "title": title, "reason": reason,
                "notes": request.POST.get("notes", "").strip(), "starts_at": starts_at,
                "ends_at": ends_at, "all_day": all_day, "entire_team": entire_team,
                # Editing time is deliberately informational under the existing design.
                "blocks_booking": kind in {ScheduleConstraint.Kind.BLOCKED, ScheduleConstraint.Kind.VACATION}
                                  and request.POST.get("prevent_booking") == "on",
            }
            with transaction.atomic():
                PhotographerProfile.objects.select_for_update().get(pk=profile.pk)
                if constraint:
                    for field, value in values.items():
                        setattr(constraint, field, value)
                    constraint.save()
                else:
                    constraint = ScheduleConstraint.objects.create(studio=profile, created_by=request.user, **values)
                constraint.assigned_members.set(member_ids)
            return JsonResponse({"ok": True, "schedule_url": reverse("photographer_workspace:schedule")},
                                status=200 if request.POST["action"] == "edit_constraint" else 201)
        if request.POST.get("action") in {"create_booking", "edit_booking", "create_consultation", "edit_consultation"}:
            is_consultation = request.POST["action"].endswith("consultation")
            is_edit = request.POST["action"].startswith("edit_")
            session = None
            if is_edit:
                editable_sessions = ClientSession.objects.filter(photographer=profile)
                if is_consultation:
                    editable_sessions = scope_assigned(editable_sessions, request.studio_access)
                session = get_object_or_404(editable_sessions, pk=request.POST.get("booking_id"))
            errors = {}
            client = Client.objects.filter(
                photographer=profile, pk=request.POST.get("contact") if is_consultation else request.POST.get("client")
            ).first()
            if client is None:
                errors["client"] = "Select a client from this workspace."
            session_type = (request.POST.get("meeting_type", "").strip() if is_consultation
                            else request.POST.get("session_type", "").strip())
            if not session_type:
                errors["session_type"] = "Enter a session type."
            try:
                starts_at = parse_local_datetime(profile, request.POST.get("start_date", ""), request.POST.get("start_time", ""))
                ends_at = parse_local_datetime(profile, request.POST.get("end_date", ""), request.POST.get("end_time", ""))
                if ends_at <= starts_at:
                    errors["end_date"] = "The end must be after the start."
            except (TypeError, ValueError):
                starts_at = ends_at = None
                errors["start_date"] = "Enter a valid start and end date and time."
            status = request.POST.get("booking_status", ClientSession.Status.TENTATIVE)
            if status not in (ClientSession.Status.TENTATIVE, ClientSession.Status.CONFIRMED):
                errors["booking_status"] = "Select a valid booking status."
            try:
                booking_value = Decimal(request.POST.get("price") or "0")
                if booking_value < 0:
                    raise ValueError
            except (ValueError, ArithmeticError):
                errors["price"] = "Enter a valid non-negative price."
            member_ids = set()
            for raw_id in request.POST.getlist("team"):
                try:
                    member_ids.add(int(raw_id))
                except (TypeError, ValueError):
                    errors["team"] = "Select active photographers from this workspace."
            valid_member_ids = set(StudioMembership.objects.filter(
                studio=profile, status=StudioMembership.Status.ACTIVE, pk__in=member_ids
            ).values_list("pk", flat=True))
            if valid_member_ids != member_ids:
                errors["team"] = "Select active photographers from this workspace."
            if errors:
                return JsonResponse({"ok": False, "errors": errors}, status=400)
            values = {
                "client": client, "session_type": session_type, "starts_at": starts_at,
                "event_kind": ClientSession.EventKind.CONSULTATION if is_consultation else ClientSession.EventKind.BOOKING,
                "duration_minutes": max(1, round((ends_at - starts_at).total_seconds() / 60)),
                "location": ((request.POST.get("meeting_format", "") + ": " + request.POST.get("meeting_location", "")).strip(": ")
                             if is_consultation else request.POST.get("location", "").strip()), "status": status,
                "booking_value": booking_value, "notes": request.POST.get("notes", "").strip(),
            }
            with transaction.atomic():
                # Serialize scheduling writes per studio. This closes the usual
                # empty-slot check/create race where there is no booking row to lock.
                PhotographerProfile.objects.select_for_update().get(pk=profile.pk)
                availability = availability_for(
                    studio=profile, starts_at=starts_at,
                    duration_minutes=values["duration_minutes"], member_ids=member_ids,
                    exclude_pk=session.pk if session else None, lock=True,
                )
                if not availability["available"]:
                    conflict_error = (
                        "This photographer already has a booking during that time."
                        if availability["conflicts"] else
                        "This time is blocked by a schedule constraint."
                        if availability["constraint_conflicts"] else
                        "This time is outside the assigned photographer's working hours."
                    )
                    return JsonResponse({"ok": False, "errors": {"start_time": conflict_error}}, status=409)
                if is_edit:
                    before = {
                        "client_id": session.client_id, "session_type": session.session_type,
                        "starts_at": session.starts_at.isoformat(), "duration_minutes": session.duration_minutes,
                        "location": session.location, "status": session.status,
                        "booking_value": str(session.booking_value), "notes": session.notes,
                        "member_ids": sorted(session.assigned_members.values_list("pk", flat=True)),
                    }
                    for field, value in values.items():
                        setattr(session, field, value)
                    session.save()
                    session.assigned_members.set(member_ids)
                    after = before | {
                        "client_id": session.client_id, "session_type": session.session_type,
                        "starts_at": session.starts_at.isoformat(), "duration_minutes": session.duration_minutes,
                        "location": session.location, "status": session.status,
                        "booking_value": str(session.booking_value), "notes": session.notes,
                        "member_ids": sorted(member_ids),
                    }
                    changes = {key: {"before": before[key], "after": after[key]} for key in before if before[key] != after[key]}
                    if changes:
                        event_type = (ClientActivity.EventType.BOOKING_RESCHEDULED
                                      if {"starts_at", "duration_minutes"} & changes.keys()
                                      else ClientActivity.EventType.BOOKING_UPDATED)
                        ClientActivity.objects.create(
                            photographer=profile, actor=request.user, client=session.client,
                            booking=session, event_type=event_type, metadata={"changes": changes},
                            description=f"{session.session_type} was {event_type.removeprefix('booking_')}.",
                        )
                else:
                    session = ClientSession.objects.create(photographer=profile, **values)
                    session.assigned_members.set(member_ids)
                    ClientActivity.objects.create(
                        photographer=profile, actor=request.user, client=client, booking=session,
                        event_type=ClientActivity.EventType.BOOKING_CREATED,
                        description=f"{session.session_type} was created.",
                    )
            return JsonResponse({
                "ok": True,
                "booking_url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
            }, status=200 if is_edit else 201)
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
    today = timezone.localdate()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    all_sessions = ClientSession.objects.filter(photographer=profile).select_related("client")
    upcoming = all_sessions.filter(starts_at__gte=now).exclude(status__in=[ClientSession.Status.CANCELLED, ClientSession.Status.COMPLETED]).order_by("starts_at")
    today_sessions = list(all_sessions.filter(starts_at__date=today).exclude(status=ClientSession.Status.CANCELLED).order_by("starts_at")[:5])

    open_invoices = ClientInvoice.objects.filter(photographer=profile).exclude(status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID])
    overdue_invoices = open_invoices.filter(due_date__lt=today)
    tentative = upcoming.filter(status=ClientSession.Status.TENTATIVE)

    focus = []
    if today_sessions:
        focus.append({"icon": "bi-camera", "tone": "info", "title": f"{len(today_sessions)} session{'s' if len(today_sessions) != 1 else ''} happening today", "detail": "Review locations and client details before each session.", "action": "View schedule", "url": reverse("photographer_workspace:calendar")})
    if overdue_invoices.exists():
        focus.append({"icon": "bi-credit-card", "tone": "danger", "title": f"{overdue_invoices.count()} overdue payment{'s' if overdue_invoices.count() != 1 else ''}", "detail": "Follow up on invoice balances that are past due.", "action": "Review payments", "url": reverse("photographer_workspace:payments")})
    if tentative.exists():
        focus.append({"icon": "bi-calendar-exclamation", "tone": "warning", "title": f"{tentative.count()} unconfirmed booking{'s' if tentative.count() != 1 else ''}", "detail": "Confirm tentative sessions so the calendar stays accurate.", "action": "Review bookings", "url": reverse("photographer_workspace:calendar")})

    revenue_periods = {"30": "30 days", "90": "90 days", "180": "6 months", "365": "12 months"}
    revenue_period = request.GET.get("period", "30")
    if revenue_period not in revenue_periods:
        revenue_period = "30"
    period_days = int(revenue_period)
    period_start = today - timedelta(days=period_days - 1)
    previous_start = period_start - timedelta(days=period_days)
    invoices = ClientInvoice.objects.filter(photographer=profile, created_at__date__range=(period_start, today)).exclude(status=ClientInvoice.Status.VOID)
    previous_total = ClientInvoice.objects.filter(photographer=profile, created_at__date__range=(previous_start, period_start - timedelta(days=1))).exclude(status=ClientInvoice.Status.VOID).aggregate(total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField()))["total"]
    revenue_total = invoices.aggregate(total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField()))["total"]
    collected = invoices.aggregate(total=Coalesce(Sum("amount_paid"), Value(Decimal("0.00")), output_field=DecimalField()))["total"]
    confirmed = invoices.exclude(status=ClientInvoice.Status.DRAFT).aggregate(total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField()))["total"]
    change = ((revenue_total - previous_total) / previous_total * 100) if previous_total else None

    stage_counts = {row["status"]: row["count"] for row in all_sessions.values("status").annotate(count=Count("id"))}
    stage_total = sum(stage_counts.values())
    booking_stages = [{"key": key, "label": label, "count": stage_counts.get(key, 0), "percent": round(stage_counts.get(key, 0) / stage_total * 100) if stage_total else 0} for key, label in ClientSession.Status.choices]

    for session in list(upcoming[:5]) + today_sessions:
        session.badge_variant = "success" if session.status == ClientSession.Status.CONFIRMED else "warning" if session.status == ClientSession.Status.TENTATIVE else "neutral"
    upcoming_bookings = list(upcoming[:5])
    for session in upcoming_bookings:
        invoice = open_invoices.filter(booking=session).order_by("due_date").first()
        session.needs_attention = session.status == ClientSession.Status.TENTATIVE or bool(invoice and invoice.balance > 0)
        session.attention_label = "Confirmation needed" if session.status == ClientSession.Status.TENTATIVE else "Payment due"

    activity_styles = {ClientActivity.EventType.LEAD_BOOKED: "bi-calendar2-check", ClientActivity.EventType.CONTRACT_SIGNED: "bi-pen", ClientActivity.EventType.PAYMENT_RECEIVED: "bi-credit-card", ClientActivity.EventType.CONSULTATION_SCHEDULED: "bi-calendar-event"}
    supported_events = list(activity_styles)
    recent_activity = [{"icon": activity_styles[activity.event_type], "description": activity.description or activity.get_event_type_display(), "related": str(activity.client or activity.lead or "Booking workspace"), "occurred_at": activity.occurred_at} for activity in ClientActivity.objects.filter(photographer=profile, event_type__in=supported_events).select_related("lead", "client")[:5]]

    context = _dashboard_context(request, "bookings", "Overview")
    context.update({
        "booking_state": request.GET.get("state") if request.GET.get("state") in {"loading", "error"} else "ready",
        "booking_metrics": [
            {"label": "Upcoming Bookings", "value": upcoming.count(), "icon": "bi-calendar2-check", "context": "Tentative and confirmed sessions"},
            {"label": "Bookings This Month", "value": all_sessions.filter(starts_at__date__gte=month_start, starts_at__date__lt=next_month).exclude(status=ClientSession.Status.CANCELLED).count(), "icon": "bi-calendar3", "context": today.strftime("%B %Y")},
            {"label": "Pending Confirmations", "value": tentative.count(), "icon": "bi-clock-history", "context": "Tentative upcoming sessions"},
            {"label": "Booking Revenue", "value": f"{profile.default_currency} {revenue_total:,.2f}", "icon": "bi-graph-up-arrow", "context": revenue_periods[revenue_period]},
        ],
        "today_focus": focus[:5], "today_sessions": today_sessions, "upcoming_bookings": upcoming_bookings,
        "booking_stages": booking_stages, "revenue_period": revenue_period, "revenue_periods": revenue_periods.items(),
        "revenue_summary": {"has_data": invoices.exists(), "total": revenue_total, "confirmed": confirmed, "pending": revenue_total - collected, "collected": collected, "change": change, "change_abs": abs(change) if change is not None else None},
        "recent_booking_activity": recent_activity,
        "booking_clients": Client.objects.filter(photographer=profile).order_by("first_name", "last_name"),
        "schedule_members": StudioMembership.objects.filter(
            studio=profile, status=StudioMembership.Status.ACTIVE
        ).select_related("user").order_by("user__first_name", "user__last_name", "invitation_first_name"),
        "studio_timezone": str(studio_timezone(profile)),
        # Keep booking creation on the shared schedule drawer rather than
        # introducing an overview-specific form or client-side workflow.
        "selected_date": today,
        "event_form_types": [
            ("booking", "Booking", "bi-camera"),
            ("consultation", "Consultation", "bi-chat-square-text"),
            ("editing", "Editing Time", "bi-magic"),
            ("blocked", "Blocked Time", "bi-slash-circle"),
            ("vacation", "Vacation", "bi-sun"),
            ("mini", "Mini Session", "bi-people"),
        ],
        "booking_quick_actions": [
            {"label": "New Booking", "icon": "bi-calendar-plus", "url": f'{reverse("photographer_workspace:bookings")}?action=new', "help": "Start a client booking"},
            {"label": "Block Time", "icon": "bi-calendar-x", "url": f'{reverse("photographer_workspace:calendar")}?action=block', "help": "Reserve unavailable time"},
            {"label": "Schedule Consultation", "icon": "bi-chat-square-text", "url": reverse("photographer_workspace:calendar"), "help": "Plan a client consultation"},
        ],
    })
    return render(request, "photographer_workspace/bookings/dashboard.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def booking_detail(request, pk):
    """Keep booking-specific documents within the booking workspace."""
    profile = request.studio
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
        "booking_activity": booking.activities.select_related("actor").all()[:20],
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
    profile = request.studio
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
    sessions_queryset = scope_assigned(ClientSession.objects.all(), request.studio_access).filter(
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
    if filter_values["member"].isdigit():
        sessions_queryset = sessions_queryset.filter(assigned_members__pk=int(filter_values["member"]))
    elif filter_values["member"] == "me" and request.studio_access.membership:
        sessions_queryset = sessions_queryset.filter(assigned_members=request.studio_access.membership)
    if filter_values["event_type"] in ClientSession.EventKind.values:
        sessions_queryset = sessions_queryset.filter(event_kind=filter_values["event_type"])
    elif filter_values["event_type"]:
        sessions_queryset = sessions_queryset.none()
    all_profile_sessions = ClientSession.objects.filter(photographer=profile)
    session_types = list(all_profile_sessions.exclude(session_type="").values_list("session_type", flat=True).distinct().order_by("session_type"))
    locations = list(all_profile_sessions.exclude(location="").values_list("location", flat=True).distinct().order_by("location"))
    sessions = list(sessions_queryset.select_related("client").prefetch_related("invoices", "assigned_members__user").order_by("starts_at"))
    owner = request.user.full_name or "Studio photographer"
    events = [{
        "id": session.pk,
        "starts_at": timezone.localtime(session.starts_at),
        "ends_at": timezone.localtime(session.starts_at) + timedelta(minutes=session.duration_minutes),
        "name": str(session.client), "session_type": session.session_type,
        "booking_number": f"LP-{session.pk:04d}", "location": session.location or "Location not set",
        "photographer": ", ".join(
            membership.user.full_name or membership.user.email
            for membership in session.assigned_members.all()
        ) or owner, "status": session.get_status_display(), "status_key": session.status,
        "kind": session.event_kind,
        "icon": "bi-chat-square-text" if session.event_kind == ClientSession.EventKind.CONSULTATION else "bi-camera",
        "warning": session.status == ClientSession.Status.TENTATIVE,
        "persisted": True, "move_url": reverse("photographer_workspace:reschedule_session", args=[session.pk]),
        "all_day": False, "url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
        "contact": " · ".join(value for value in (session.client.email, session.client.phone) if value) or "No contact information",
        "contact_email": session.client.email, "contact_phone": session.client.phone,
        "package": "Not assigned", "contract_status": "Not tracked",
        "payment_status": (
            "Not invoiced" if not session.invoices.all()
            else "Paid" if all(invoice.status in (ClientInvoice.Status.PAID, ClientInvoice.Status.VOID) for invoice in session.invoices.all())
            else "Payment due"
        ), "questionnaire_status": "Not tracked",
        "notes": session.notes,
        "client_id": session.client_id, "booking_value": str(session.booking_value),
        "member_ids": [membership.pk for membership in session.assigned_members.all()],
        "warnings": (
            (["Session is tentative"] if session.status == ClientSession.Status.TENTATIVE else [])
            + (["Payment requires attention"] if session.invoices.all() and any(invoice.status not in (ClientInvoice.Status.PAID, ClientInvoice.Status.VOID) for invoice in session.invoices.all()) else [])
        ),
    } for session in sessions]

    if not filter_values["event_type"] or filter_values["event_type"] == "mini":
        minis = MiniSession.objects.for_photographer(profile).filter(
            starts_at__date__gte=range_start, starts_at__date__lt=range_end,
        )
        if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
            minis = minis.filter(assigned_members=request.studio_access.membership)
        if not filter_values["show_cancelled"]:
            minis = minis.exclude(status=MiniSession.Status.CANCELLED)
        for mini in minis.prefetch_related("assigned_members__user", "slots__bookings"):
            members = list(mini.assigned_members.all())
            events.append({
                "id": f"mini-{mini.pk}", "mini_id": mini.pk,
                "starts_at": timezone.localtime(mini.starts_at, studio_timezone(profile)),
                "ends_at": timezone.localtime(mini.starts_at, studio_timezone(profile)) + timedelta(minutes=mini.duration_minutes),
                "name": mini.name, "session_type": mini.service or "Mini session",
                "booking_number": "", "location": mini.location,
                "photographer": ", ".join(member.user.full_name or member.user.email for member in members) or owner,
                "status": mini.get_status_display(), "status_key": mini.status, "kind": "mini", "icon": "bi-people",
                "warning": False, "persisted": True, "move_url": "", "all_day": False, "url": "",
                "contact": f"{mini.slots.count()} slots · capacity {mini.capacity_per_slot} each",
                "contact_email": "", "contact_phone": "", "package": mini.service or "Not assigned",
                "contract_status": "Not tracked", "payment_status": "Not tracked", "questionnaire_status": "Not tracked",
                "notes": mini.notes, "client_id": "", "booking_value": "0",
                "member_ids": [member.pk for member in members], "warnings": [],
                "slot_duration": mini.slot_duration_minutes, "slot_count": mini.slot_count,
                "buffer": mini.buffer_minutes, "capacity": mini.capacity_per_slot,
            })

    range_starts_at = parse_local_datetime(profile, range_start.isoformat(), "00:00")
    range_ends_at = parse_local_datetime(profile, range_end.isoformat(), "00:00")
    constraints_queryset = ScheduleConstraint.objects.filter(
        studio=profile, starts_at__lt=range_ends_at, ends_at__gt=range_starts_at,
    ).prefetch_related("assigned_members__user")
    if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
        constraints_queryset = constraints_queryset.filter(
            Q(entire_team=True) | Q(assigned_members=request.studio_access.membership)
        ).distinct()
    if filter_values["event_type"] == "booking":
        constraints_queryset = constraints_queryset.none()
    elif filter_values["event_type"]:
        constraints_queryset = constraints_queryset.filter(kind=filter_values["event_type"])
    constraint_icons = {"blocked": "bi-slash-circle", "editing": "bi-magic", "vacation": "bi-sun"}
    for constraint in constraints_queryset:
        local_start = timezone.localtime(constraint.starts_at, studio_timezone(profile))
        local_end = timezone.localtime(constraint.ends_at, studio_timezone(profile))
        members = list(constraint.assigned_members.all())
        events.append({
            "id": f"constraint-{constraint.pk}", "constraint_id": constraint.pk,
            "starts_at": local_start, "ends_at": local_end,
            "name": constraint.title, "session_type": constraint.get_kind_display(),
            "booking_number": "", "location": "Away" if constraint.kind == "vacation" else "",
            "photographer": "Entire team" if constraint.entire_team else ", ".join(
                member.user.full_name or member.email for member in members
            ) or owner,
            "status": "Blocks bookings" if constraint.blocks_booking else "Informational",
            "status_key": "blocking" if constraint.blocks_booking else "informational",
            "kind": constraint.kind, "icon": constraint_icons[constraint.kind], "warning": False,
            "persisted": True, "all_day": constraint.all_day, "url": "",
            "contact": "", "contact_email": "", "contact_phone": "", "package": "",
            "contract_status": "", "payment_status": "", "questionnaire_status": "",
            "notes": constraint.notes, "reason": constraint.reason, "client_id": None,
            "booking_value": "", "member_ids": [member.pk for member in members], "warnings": [],
        })

    # Production schedule surfaces only persisted, studio-scoped records.
    using_sample_events = False

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
        minutes = round((event["ends_at"] - event["starts_at"]).total_seconds() / 60)
        hours, remaining_minutes = divmod(minutes, 60)
        event["duration"] = " ".join(part for part in (
            f"{hours} hr" if hours else "", f"{remaining_minutes} min" if remaining_minutes else "",
        ) if part)
        if event["kind"] in ("booking", "consultation"):
            noun = "Consultation" if event["kind"] == "consultation" else "Booking"
            event["actions"] = [
                *([{"label": "Open Full Booking", "type": "link", "url": event["url"], "priority": "primary", "icon": "bi-box-arrow-up-right"}] if event["kind"] == "booking" else []),
                *([{"label": "Contact Client", "type": "link", "url": f'mailto:{event["contact_email"]}', "priority": "secondary", "icon": "bi-envelope"}] if event["contact_email"] else []),
                {"label": f"Edit {noun}", "type": "edit", "priority": "secondary", "icon": "bi-pencil"},
                *([{"label": "Reschedule", "type": "reschedule", "priority": "secondary", "icon": "bi-calendar3"}] if event["status_key"] not in (ClientSession.Status.COMPLETED, ClientSession.Status.CANCELLED) else []),
                *([{"label": "Mark Complete", "type": "post", "url": reverse("photographer_workspace:booking_action", args=[event["id"]]), "value": "mark_complete", "priority": "workflow", "icon": "bi-check2-circle"}] if event["status_key"] in (ClientSession.Status.TENTATIVE, ClientSession.Status.CONFIRMED) else []),
                *([{"label": "Create Gallery", "type": "link", "url": reverse("photographer_workspace:create_gallery"), "priority": "workflow", "icon": "bi-images"}] if event["status_key"] == ClientSession.Status.COMPLETED else []),
                *([{"label": f"Cancel {noun}", "type": "post", "url": reverse("photographer_workspace:booking_action", args=[event["id"]]), "value": "cancel", "priority": "destructive", "icon": "bi-x-circle"}] if event["status_key"] != ClientSession.Status.CANCELLED else []),
            ]
        elif event["kind"] == "mini":
            event["actions"] = [
                {"label": "Edit Mini Session", "type": "edit", "priority": "secondary", "icon": "bi-pencil"},
                *([{"label": "Cancel Mini Session", "type": "post",
                   "url": reverse("photographer_workspace:mini_session_action", args=[event["mini_id"]]),
                   "value": "cancel", "priority": "destructive", "icon": "bi-x-circle"}]
                  if event["status_key"] != MiniSession.Status.CANCELLED else []),
            ]
        else:
            event["actions"] = [
                {"label": f"Edit {event['session_type']}", "type": "edit", "priority": "secondary", "icon": "bi-pencil"},
                {"label": "Remove", "type": "post",
                 "url": reverse("photographer_workspace:constraint_action", args=[event["constraint_id"]]),
                 "value": "delete", "priority": "destructive", "icon": "bi-trash"},
            ]

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
        event_day = event["starts_at"].date()
        final_day = (event["ends_at"] - timedelta(microseconds=1)).date()
        while event_day <= final_day:
            events_by_date.setdefault(event_day, []).append(event)
            event_day += timedelta(days=1)

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
        "booking_clients": Client.objects.filter(photographer=profile).order_by("first_name", "last_name"),
        "schedule_members": StudioMembership.objects.filter(
            studio=profile, status=StudioMembership.Status.ACTIVE
        ).select_related("user").order_by("user__first_name", "user__last_name", "invitation_first_name"),
        "studio_timezone": str(studio_timezone(profile)),
        "booking_status_options": ClientSession.Status.choices,
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

    profile = request.studio
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

    local_start = timezone.localtime(starts_at, studio_timezone(profile))
    end = starts_at + timedelta(minutes=duration)
    member_ids = set(session.assigned_members.values_list("pk", flat=True))
    result = availability_for(studio=profile, starts_at=starts_at, duration_minutes=duration,
                              member_ids=member_ids, exclude_pk=session.pk)
    conflicts = [f"{other.client} · {timezone.localtime(other.starts_at).strftime('%b %-d, %-I:%M %p')}"
                 for other in result["conflicts"]]
    checks = [
        {"key": "conflict", "label": "Booking conflicts", "ok": not conflicts, "detail": "No overlapping bookings" if not conflicts else ", ".join(conflicts)},
        {"key": "availability", "label": "Photographer availability", "ok": result["working_hours_ok"], "detail": "Within configured working hours" if result["working_hours_ok"] else "Outside the photographer's configured working hours"},
    ]
    blocking = not result["available"]
    response = {"starts_at": local_start.isoformat(), "ends_at": timezone.localtime(end).isoformat(), "checks": checks,
                "blocking": blocking, "notify_recommended": session.status == ClientSession.Status.CONFIRMED}
    if payload.get("preview", True):
        return JsonResponse(response)
    if blocking:
        return JsonResponse(response | {"error": "Resolve booking conflicts or working hours before saving."}, status=409)
    with transaction.atomic():
        PhotographerProfile.objects.select_for_update().get(pk=profile.pk)
        locked = ClientSession.objects.select_for_update().get(pk=session.pk, photographer=profile)
        locked_members = set(locked.assigned_members.values_list("pk", flat=True))
        locked_result = availability_for(
            studio=profile, starts_at=starts_at, duration_minutes=duration,
            member_ids=locked_members, exclude_pk=locked.pk, lock=True,
        )
        if not locked_result["available"]:
            return JsonResponse(response | {"blocking": True, "error": "The slot became unavailable. Refresh and choose another time."}, status=409)
        before = {"starts_at": locked.starts_at.isoformat(), "duration_minutes": locked.duration_minutes}
        locked.starts_at, locked.duration_minutes = starts_at, duration
        locked.save(update_fields=("starts_at", "duration_minutes", "updated_at"))
        after = {"starts_at": locked.starts_at.isoformat(), "duration_minutes": locked.duration_minutes}
        if before != after:
            ClientActivity.objects.create(
                photographer=profile, actor=request.user, client=locked.client, booking=locked,
                event_type=ClientActivity.EventType.BOOKING_RESCHEDULED,
                description=f"{locked.session_type} was rescheduled.",
                metadata={"changes": {key: {"before": before[key], "after": after[key]} for key in before if before[key] != after[key]}},
            )
    return JsonResponse(response | {"saved": True, "notified": bool(payload.get("notify_client"))})


@photographer_workspace_required
@require_POST
def booking_action(request, pk):
    """Apply the state transitions supported by the schedule inspector."""
    sessions = ClientSession.objects.filter(photographer=request.studio)
    candidate = get_object_or_404(sessions, pk=pk)
    if candidate.event_kind == ClientSession.EventKind.CONSULTATION:
        candidate = get_object_or_404(scope_assigned(sessions, request.studio_access), pk=pk)
    session = candidate
    action = request.POST.get("action")
    if action == "mark_complete" and session.status in (ClientSession.Status.TENTATIVE, ClientSession.Status.CONFIRMED):
        session.status = ClientSession.Status.COMPLETED
        session.save(update_fields=("status", "updated_at"))
        messages.success(request, f"{session.session_type} for {session.client} marked complete.")
    elif action == "cancel" and session.status != ClientSession.Status.CANCELLED:
        session.status = ClientSession.Status.CANCELLED
        session.cancelled_at = timezone.now()
        session.cancellation_reason = request.POST.get("reason", "").strip()[:500]
        session.save(update_fields=("status", "cancelled_at", "cancellation_reason", "updated_at"))
        ClientActivity.objects.create(
            photographer=request.studio, actor=request.user, client=session.client, booking=session,
            event_type=ClientActivity.EventType.BOOKING_CANCELLED,
            description=f"{session.session_type} was cancelled.",
            metadata={"reason": session.cancellation_reason},
        )
        messages.success(request, f"{session.session_type} for {session.client} cancelled.")
    else:
        messages.error(request, "That booking action is not available in its current state.")
    return redirect("photographer_workspace:schedule")


@photographer_workspace_required
@require_POST
def mini_slot_book(request, pk):
    """Atomically assign a workspace client without exceeding persisted slot capacity."""
    profile = request.studio
    client = get_object_or_404(Client.objects.for_photographer(profile), pk=request.POST.get("client"))
    with transaction.atomic():
        PhotographerProfile.objects.select_for_update().get(pk=profile.pk)
        slot = get_object_or_404(
            MiniSessionSlot.objects.select_for_update().select_related("mini_session"),
            pk=pk, mini_session__photographer=profile, mini_session__status=MiniSession.Status.ACTIVE,
            cancelled_at__isnull=True,
        )
        if (request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER and
                not slot.mini_session.assigned_members.filter(pk=request.studio_access.membership.pk).exists()):
            raise PermissionDenied
        if slot.bookings.filter(cancelled_at__isnull=True).count() >= slot.mini_session.capacity_per_slot:
            return JsonResponse({"ok": False, "error": "This mini-session slot is full."}, status=409)
        booking, created = MiniSessionSlotBooking.objects.get_or_create(
            photographer=profile, slot=slot, client=client,
        )
        if not created and booking.cancelled_at is None:
            return JsonResponse({"ok": False, "error": "This client is already booked into the slot."}, status=409)
        if not created:
            booking.cancelled_at = None
            booking.save(update_fields=("cancelled_at",))
    return JsonResponse({"ok": True}, status=201)


@photographer_workspace_required
@require_POST
def mini_session_action(request, pk):
    minis = MiniSession.objects.for_photographer(request.studio)
    if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
        minis = minis.filter(assigned_members=request.studio_access.membership)
    mini = get_object_or_404(minis, pk=pk)
    action = request.POST.get("action")
    if action == "cancel":
        now = timezone.now()
        with transaction.atomic():
            mini.status = MiniSession.Status.CANCELLED
            mini.cancelled_at = now
            mini.save(update_fields=("status", "cancelled_at", "updated_at"))
            MiniSessionSlotBooking.objects.filter(
                photographer=request.studio, slot__mini_session=mini, cancelled_at__isnull=True,
            ).update(cancelled_at=now)
        messages.success(request, "Mini session and its active slot bookings cancelled.")
    else:
        return HttpResponseBadRequest("Unsupported mini-session action.")
    return redirect("photographer_workspace:schedule")


@photographer_workspace_required
@require_POST
def constraint_action(request, pk):
    """Delete a studio-scoped schedule constraint with role/resource enforcement."""
    if not request.studio_access.allows("schedule"):
        raise PermissionDenied
    constraint = get_object_or_404(ScheduleConstraint, pk=pk, studio=request.studio)
    if request.studio_access.role == StudioMembership.Role.PHOTOGRAPHER:
        membership = request.studio_access.membership
        if constraint.entire_team or not constraint.assigned_members.filter(pk=membership.pk).exists():
            raise PermissionDenied
    if request.POST.get("action") != "delete":
        return HttpResponseBadRequest("Unsupported schedule action.")
    constraint.delete()
    messages.success(request, "Schedule event removed. The time is available again.")
    return redirect("photographer_workspace:schedule")


@photographer_workspace_required
@require_GET
def analytics_overview(request):
    """Render owner-scoped analytics directly from operational records."""
    context = _dashboard_context(request, "analytics", "Analytics")
    context.update(build_analytics_overview(request.studio, request.GET, request.path))
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
    profile = request.studio
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
    metrics = growth_summary(request.studio, range_key,
                             getattr(request.studio, "default_currency", "USD"))
    for card in metrics["cards"]:
        card["url"] = f'{card["url"]}?range={range_key}'
    source_sort = request.GET.get("source_sort", "leads")
    currency = getattr(request.studio, "default_currency", "USD")
    source_metric = request.GET.get("source_metric", "booking_value")
    show_all_sources = request.GET.get("show_all_sources") == "1"
    section_states = {}
    for section in ("funnel", "sources", "services", "reviews", "activity"):
        state = request.GET.get(f"{section}_state", "ready")
        section_states[section] = state if state in {"ready", "loading", "empty", "error", "permission"} else "ready"
    context.update({
        "growth_state": page_state,
        "range_key": range_key,
        "range_options": range_options,
        "compare_previous": request.GET.get("compare") == "1",
        "growth_metrics": metrics["cards"],
        "funnel_stages": [stage | {"url": f'{stage["url"]}&range={range_key}'}
                          for stage in lead_funnel(request.studio, range_key, currency)],
        "source_rows": lead_source_performance(request.studio, range_key, currency, source_sort),
        "source_sort": source_sort,
        "source_chart": booking_value_by_source(request.studio, range_key, source_metric,
                                                 show_all_sources, currency),
        "show_all_sources": show_all_sources,
        "service_rows": service_performance(request.studio, range_key, currency),
        "section_states": section_states,
        "reviews": reputation_summary(request.studio, range_key),
        "referrals": referral_summary(request.studio, range_key, currency),
        "retention": retention_summary(request.studio, range_key, currency),
        "opportunities": growth_opportunities(request.studio,
                                                request.GET.get("show_all_opportunities") == "1"),
        "recent_growth_activity": recent_growth_activity(request.studio),
        "recent_campaigns": GrowthCampaign.objects.for_photographer(request.studio)[:5],
    })
    return render(request, "photographer_workspace/growth/overview.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def growth_action(request):
    """Create deliberately small, studio-scoped growth records."""
    profile = request.studio
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
    range_key = request.GET.get("range") or request.POST.get("range") or "last_30_days"
    context = _dashboard_context(request, "growth", "Promote your business")
    context.update({"growth_action": action, "range_key": range_key,
                    "eligible_bookings": completed_bookings.exclude(review_requests__isnull=False),
                    "selected_booking_ids": request.POST.getlist("bookings"),
                    "review_message": request.POST.get("message", "Thank you for choosing our studio. We’d appreciate a quick review of your experience."),
                    "clients": Client.objects.for_photographer(profile).order_by("first_name", "last_name"),
                    "campaigns": GrowthCampaign.objects.for_photographer(profile),
                    "referral_types": ReferralLink.ReferralType.choices, "referral_statuses": ReferralLink.Status.choices,
                    "campaign_statuses": GrowthCampaign.Status.choices})
    return render(request, "photographer_workspace/growth/action.html", context)


@photographer_workspace_required
@require_GET
def growth_export(request):
    """Export all date-scoped growth sections as a portable CSV report."""
    profile, range_key = request.studio, request.GET.get("range", "last_30_days")
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

    profile = request.studio
    currency = getattr(profile, "default_currency", "USD")
    summary = financial_summary(profile, range_key, currency)
    values = summary["values"]
    summary_items = [
        {"label": "Total Revenue", "value": format_currency(values["net_revenue"], currency), "icon": "bi-graph-up-arrow"},
        {"label": "Payments Received", "value": format_currency(values["collected"], currency), "icon": "bi-cash-coin"},
        {"label": "Outstanding Balance", "value": format_currency(values["outstanding"], currency), "icon": "bi-hourglass-split"},
        {"label": "Refunded", "value": format_currency(values["refunds"], currency), "icon": "bi-arrow-counterclockwise"},
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
    profile = request.studio
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
        rows = selected_objects(request.studio, values)
        if action == "capabilities":
            return JsonResponse({"actions": available_actions(rows)})
        if action == "download":
            payload = invoice_zip(request.studio, values, lambda invoice:
                render_to_string("photographer_workspace/invoices/print.html", {"invoice": invoice}))
            response = HttpResponse(payload, content_type="application/zip")
            response["Content-Disposition"] = 'attachment; filename="lumispixel-invoices.zip"'
            return response
        count = run_bulk_action(request.studio, values, action, request.POST.get("note", ""))
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
        record, duplicate = handlers[action](request.studio, request.POST)
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
    detail = financial_record_detail(request.studio, record_type, pk,
                                     getattr(request.studio, "default_currency", "USD"))
    if detail is None:
        return JsonResponse({"error": "This financial record was not found."}, status=404)
    html = render_to_string("photographer_workspace/financial/_record_detail.html", {"record": detail}, request=request)
    return JsonResponse({"html": html, "reference": detail["reference"]})


def _invoice_context(request, invoice=None, errors=None):
    profile = request.studio
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
    profile = request.studio
    today = timezone.localdate()
    invoices = ClientInvoice.objects.for_photographer(profile).select_related("client", "booking")
    total_count = invoices.count()
    overdue_query = Q(due_date__lt=today, status__in=[ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID])
    summary = {
        "draft": invoices.filter(status=ClientInvoice.Status.DRAFT).count(),
        "sent": invoices.filter(status=ClientInvoice.Status.SENT).exclude(overdue_query).count(),
        "outstanding": invoices.filter(status__in=[ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID]).count(),
        "overdue": invoices.filter(overdue_query).count(),
        "paid": invoices.filter(status=ClientInvoice.Status.PAID).count(),
    }
    selected = {key: request.GET.get(key, "").strip() for key in ("q", "status", "client", "due_from", "due_to")}
    if selected["q"]:
        invoices = invoices.filter(
            Q(invoice_number__icontains=selected["q"]) | Q(client__first_name__icontains=selected["q"]) |
            Q(client__last_name__icontains=selected["q"]) | Q(client__company__icontains=selected["q"]) |
            Q(booking__session_type__icontains=selected["q"])
        )
    if selected["status"] == "overdue":
        invoices = invoices.filter(overdue_query)
    elif selected["status"] in ClientInvoice.Status.values:
        invoices = invoices.filter(status=selected["status"])
    if selected["client"].isdigit():
        invoices = invoices.filter(client_id=selected["client"])
    for key, lookup in (("due_from", "due_date__gte"), ("due_to", "due_date__lte")):
        if selected[key]:
            try:
                invoices = invoices.filter(**{lookup: date.fromisoformat(selected[key])})
            except ValueError:
                selected[key] = ""
    active_filters = any(selected.values())
    page = Paginator(invoices.order_by("due_date", "-created_at"), 15).get_page(request.GET.get("page"))
    for invoice in page:
        invoice.is_overdue = invoice.due_date and invoice.due_date < today and invoice.status in {
            ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID}
    context = _dashboard_context(request, "invoices", "Invoices")
    context.update({"invoices": page, "invoice_total_count": total_count, "invoice_summary": summary,
                    "invoice_filters": selected, "invoice_filters_active": active_filters,
                    "invoice_filters_query": urlencode({key: value for key, value in selected.items() if value}),
                    "invoice_clients": Client.objects.for_photographer(profile).filter(invoices__isnull=False).distinct().order_by("first_name", "last_name")})
    return render(request, "photographer_workspace/invoices/list.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def invoice_create(request):
    if request.method == "POST":
        try:
            invoice = save_invoice(request.studio, request.POST, send=request.POST.get("intent") == "send")
            messages.success(request, f"{invoice.invoice_number} was {'sent' if invoice.status == ClientInvoice.Status.SENT else 'saved as a draft'}.")
            return redirect("photographer_workspace:invoice_view", pk=invoice.pk)
        except ValidationError as exc:
            return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request, errors=exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}), status=400)
    return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request))


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def invoice_edit(request, pk):
    invoice = get_object_or_404(ClientInvoice.objects.for_photographer(request.studio).prefetch_related("line_items", "payment_schedule"), pk=pk)
    if invoice.status != ClientInvoice.Status.DRAFT:
        messages.error(request, "Only draft invoices can be edited.")
        return redirect("photographer_workspace:invoice_view", pk=pk)
    if request.method == "POST":
        try:
            invoice = save_invoice(request.studio, request.POST, invoice, request.POST.get("intent") == "send")
            messages.success(request, "Invoice updated.")
            return redirect("photographer_workspace:invoice_view", pk=pk)
        except ValidationError as exc:
            return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request, invoice, exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}), status=400)
    return render(request, "photographer_workspace/invoices/form.html", _invoice_context(request, invoice))


@photographer_workspace_required
@require_GET
def invoice_view(request, pk):
    invoice = get_object_or_404(ClientInvoice.objects.for_photographer(request.studio).select_related("client", "booking").prefetch_related("line_items", "payment_schedule", "activity"), pk=pk)
    return render(request, "photographer_workspace/invoices/detail.html", _invoice_context(request, invoice))


@photographer_workspace_required
@require_POST
def invoice_action(request, pk, action):
    profile = request.studio
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
    invoice = get_object_or_404(ClientInvoice.objects.for_photographer(request.studio).select_related("client").prefetch_related("line_items"), pk=pk)
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
    if page_key == "team_performance":
        return team_performance(request)
    title, subtitle, icon = TEAM_PAGES[page_key]
    context = _dashboard_context(request, page_key, title)
    context["team_page"] = {"title": title, "subtitle": subtitle, "icon": icon}
    return render(request, "photographer_workspace/team/temporary_page.html", context)


def team_performance(request):
    can_view_financials = request.studio_access.allows("financials")
    report = team_performance_report(authorized_studio(request.user), request.GET,
                                     can_view_financials=can_view_financials)
    preserved = request.GET.copy()
    preserved.pop("page", None)
    preserved.pop("export", None)
    report["filter_query"] = preserved.urlencode()
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="team-performance-{report["start"]}-{report["end"]}.csv"'
        writer = csv.writer(response)
        headers = ["Team member", "Role", "Location", "Bookings", "Completed", "Completion rate", "Hours", "Galleries delivered", "Average turnaround days"]
        if can_view_financials:
            headers.append("Revenue contribution")
        writer.writerow(headers)
        # Export the complete filtered comparison, not merely the visible page.
        for row in report["export_rows"]:
            values = [row["name"], row["role"], row["location"], row["bookings"], row["completed"], row["completion_rate"] if row["completion_rate"] is not None else "", row["hours"], row["galleries"], row["turnaround"] if row["turnaround"] is not None else ""]
            if can_view_financials:
                values.append(row["revenue"])
            writer.writerow(values)
        return response
    context = _dashboard_context(request, "team_performance", "Team Performance")
    context.update(report)
    return render(request, "photographer_workspace/team/performance.html", context)


@photographer_workspace_required
@require_GET
def team_performance_member(request, pk):
    """Read-only performance drill-down; source tools remain the place for edits."""
    studio = authorized_studio(request.user)
    membership = get_object_or_404(StudioMembership.objects.select_related("user"), studio=studio, pk=pk)
    can_view_financials = request.studio_access.allows("financials")
    report = team_performance_report(studio, {**request.GET.dict(), "member": str(pk), "status": membership.status},
                                     can_view_financials=can_view_financials)
    start, end = report["start"], report["end"]
    prior_start, prior_end = _comparison_dates(start, end, "previous")
    current = calculate_period_metrics(studio, [membership], start, end, include_financials=can_view_financials)
    previous = calculate_period_metrics(studio, [membership], prior_start, prior_end,
                                        include_financials=can_view_financials)
    active_team = list(StudioMembership.objects.filter(studio=studio, status=StudioMembership.Status.ACTIVE))
    team = calculate_period_metrics(studio, active_team, start, end, include_financials=can_view_financials)
    member_query = urlencode({"member": pk})
    urls = {"bookings": f'{reverse("photographer_workspace:bookings")}?{member_query}',
            "galleries": f'{reverse("photographer_workspace:galleries")}?{member_query}',
            "schedule": f'{reverse("photographer_workspace:schedule")}?{member_query}',
            "profile": reverse("photographer_workspace:team_member_detail", args=[pk]), "activity": "#activity"}
    upcoming = list(ClientSession.objects.for_photographer(studio).filter(
        assigned_members=membership, starts_at__gte=timezone.now()).exclude(
        status=ClientSession.Status.CANCELLED).select_related("client").order_by("starts_at")[:6])
    period_sessions = sorted(current["sessions"], key=lambda item: item.starts_at, reverse=True)
    completed = [item for item in period_sessions if item.status == ClientSession.Status.COMPLETED]
    activity = [{"title": event.action.replace("_", " ").title(), "detail": "Member profile update",
                 "at": event.occurred_at, "icon": "bi-person-gear"} for event in membership.change_events.all()[:8]]
    activity += [{"title": session.get_status_display(), "detail": session.session_type or "Assigned booking",
                  "at": session.starts_at, "icon": "bi-calendar-check"} for session in period_sessions[:5]]
    activity.sort(key=lambda item: item["at"], reverse=True)
    name = membership.user.full_name if membership.user_id else membership.email
    context = _dashboard_context(request, "team_performance", f"{name} Performance")
    context.update(report)
    context.update({"membership": membership, "member_name": name,
                    "member_initials": "".join(part[0] for part in name.split()[:2]).upper() or "TM",
                    "current": current, "previous": previous, "upcoming": upcoming,
                    "completed_assignments": completed[:6], "member_activity": activity[:10], "source_urls": urls,
                    "insights": build_member_insights(current, previous, team, urls), "insight_rules": INSIGHT_RULES,
                    "prior_start": prior_start, "prior_end": prior_end})
    return render(request, "photographer_workspace/team/performance_member.html", context)


def team_members(request):
    """Paginated, owner-scoped directory backed by memberships and user records."""
    profile = authorized_studio(request.user)
    StudioMembership.objects.filter(studio=profile, status=StudioMembership.Status.INVITED,
                                    invitation_expires_at__lte=timezone.now()).update(
        status=StudioMembership.Status.EXPIRED, invitation_token_digest="", updated_at=timezone.now())
    query = (request.GET.get("q", "") or "").strip()[:150]
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")
    location_filter = (request.GET.get("location", "") or "").strip()[:150]
    availability = request.GET.get("availability", "")
    specialty = request.GET.get("specialty", "")
    sort = request.GET.get("sort", "name")
    valid_roles = {"", "owner", *(choice[0] for choice in StudioMembership.Role.choices)}
    valid_statuses = {"", *(choice[0] for choice in StudioMembership.Status.choices)}
    if role not in valid_roles: role = ""
    if status not in valid_statuses: status = ""
    if availability not in {"", *(choice[0] for choice in StudioMembership.Availability.choices)}: availability = ""
    if sort not in {"name", "role", "status", "location", "recent"}: sort = "name"

    name = request.user.full_name or profile.display_name or request.user.email
    location = ", ".join(part for part in (profile.city, profile.state, profile.country) if part)
    # Keep directory locations concise while retaining the persisted value for filtering and tooltips.
    us_states = {"Kansas": "KS", "Oregon": "OR"}
    compact_state = us_states.get(profile.state, profile.state)
    compact_location = ", ".join(part for part in (profile.city, compact_state) if part) or "Not configured"
    owner = {
        "name": name,
        "email": request.user.email,
        "initials": "".join(part[0] for part in name.split()[:2]).upper() or "LP",
        "role": "Owner",
        "permission_summary": ACCESS_SUMMARIES[StudioMembership.Role.OWNER],
        "status": "Active" if request.user.can_login else "Inactive",
        "location": compact_location,
        "full_location": location or "Not configured",
        "availability": "Not configured",
        "availability_code": "not_configured",
        "status_code": "active" if request.user.can_login else "inactive",
        "specialties": list(profile.specialties.values_list("name", flat=True)),
        "assignment": "No assignment recorded",
        "last_active": request.user.last_login,
        "is_owner": True,
        "can_manage": True,
    }
    owner_matches = (
        (not query or query.casefold() in f"{name} {request.user.email}".casefold())
        and (not role or role == "owner")
        and (not status or status == owner["status"].casefold())
        and (not location_filter or location_filter == (location or "Not configured"))
        and (not availability or availability == "not_configured")
        and (not specialty or specialty in {str(pk) for pk in profile.specialties.values_list("pk", flat=True)})
    )
    memberships = StudioMembership.objects.filter(studio=profile).exclude(
        status=StudioMembership.Status.INVITED
    ).select_related("user").prefetch_related("specialties")
    if query:
        memberships = memberships.filter(Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) |
                                         Q(user__email__icontains=query) | Q(invitation_email__icontains=query))
    if role and role != "owner": memberships = memberships.filter(role=role)
    elif role == "owner": memberships = memberships.none()
    if status: memberships = memberships.filter(status=status)
    if location_filter: memberships = memberships.filter(primary_location=location_filter)
    if availability: memberships = memberships.filter(availability=availability)
    if specialty: memberships = memberships.filter(specialties__pk=specialty)
    ordering = {"name": ("user__first_name", "user__last_name", "invitation_email"), "role": ("role",),
                "status": ("status",), "location": ("primary_location",), "recent": ("-created_at",)}[sort]
    memberships = memberships.order_by(*ordering).distinct()
    paginator = Paginator(memberships, 23 if owner_matches else 24)
    page_obj = paginator.get_page(request.GET.get("page"))
    members = [owner] if owner_matches and page_obj.number == 1 else []
    for membership in page_obj.object_list:
        member_user = membership.user
        member_name = (member_user.full_name or member_user.email) if member_user else membership.invitation_email
        members.append({
            "id": membership.pk,
            "name": member_name, "email": membership.email,
            "initials": "".join(part[0] for part in member_name.split()[:2]).upper() or "LP",
            "role": membership.get_role_display(), "status": membership.get_status_display(),
            "permission_summary": ACCESS_SUMMARIES[membership.role],
            "location": (membership.primary_location or "Not configured").replace(", Kansas, United States", ", KS").replace(", Oregon, United States", ", OR"),
            "full_location": membership.primary_location or "Not configured",
            "availability": {
                StudioMembership.Availability.LIMITED: "Unavailable",
                StudioMembership.Availability.AWAY: "On leave",
            }.get(membership.availability, membership.get_availability_display()),
            "availability_code": membership.availability,
            "status_code": membership.status,
            "specialties": [item.name for item in membership.specialties.all()],
            "assignment": membership.current_assignment or "No assignment recorded",
            "last_active": member_user.last_login if member_user else None,
            "is_owner": False, "can_manage": True,
        })
    locations = list(StudioMembership.objects.filter(studio=profile).exclude(primary_location="")
                     .order_by("primary_location").values_list("primary_location", flat=True).distinct())
    owner_location = location or "Not configured"
    if owner_location not in locations: locations.insert(0, owner_location)
    base_params = request.GET.copy(); base_params.pop("page", None)
    active_filters = []
    labels = {"q": query, "role": dict(StudioMembership.Role.choices).get(role, "Owner" if role == "owner" else ""),
              "status": dict(StudioMembership.Status.choices).get(status, ""), "location": location_filter,
              "availability": dict(StudioMembership.Availability.choices).get(availability, "")}
    for key, label in labels.items():
        if label:
            params = base_params.copy(); params.pop(key, None)
            active_filters.append({"label": label, "url": f"?{params.urlencode()}" if params else request.path})
    context = _dashboard_context(request, "team_members", "Team Members")
    pending_invitations = StudioMembership.objects.filter(
        studio=profile, status=StudioMembership.Status.INVITED
    ).select_related("invited_by").order_by("-invitation_sent_at")
    context.update({
        "members": members,
        "owner": owner,
        "query": query,
        "selected_role": role,
        "selected_status": status,
        "selected_location": location_filter, "selected_availability": availability,
        "selected_specialty": specialty, "selected_sort": sort,
        "role_choices": [choice for choice in StudioMembership.Role.choices if choice[0] != StudioMembership.Role.OWNER],
        "status_choices": StudioMembership.Status.choices,
        "availability_choices": [
            (value, {StudioMembership.Availability.LIMITED: "Unavailable",
                     StudioMembership.Availability.AWAY: "On leave"}.get(value, label))
            for value, label in StudioMembership.Availability.choices
        ], "locations": locations,
        "specialty_choices": profile.specialties.model.objects.all().order_by("name"),
        "active_filters": active_filters, "page_obj": page_obj,
        "pagination_query": base_params.urlencode(), "total_members": paginator.count + (1 if owner_matches else 0),
        "is_solo": not StudioMembership.objects.filter(studio=profile).exists(), "can_invite": True,
        "invitation_form": InvitationForm(studio=profile),
        "role_summaries": ROLE_SUMMARIES,
        "pending_invitations": pending_invitations,
        "summary": {
            "total": StudioMembership.objects.filter(studio=profile).exclude(status="invited").count() + 1,
            "active": StudioMembership.objects.filter(studio=profile, status="active").count() + (1 if request.user.can_login else 0),
            "managers": StudioMembership.objects.filter(studio=profile, role="studio_manager").count(),
            "photographers": StudioMembership.objects.filter(studio=profile, role="photographer").count(),
            "pending": StudioMembership.objects.filter(studio=profile, status="invited").count(),
            "inactive": StudioMembership.objects.filter(studio=profile, status__in=("inactive", "access_suspended")).count() + (0 if request.user.can_login else 1),
        },
    })
    return render(request, "photographer_workspace/team/members.html", context)


@photographer_workspace_required
def team_member_detail(request, pk):
    """Show and update studio-owned member metadata without touching account credentials."""
    profile = authorized_studio(request.user)
    actor_access = access_for(request.user, studio=profile, require="manage_members")
    membership = get_object_or_404(
        StudioMembership.objects.select_related("user").prefetch_related("specialties", "change_events__actor"),
        pk=pk, studio=profile,
    )
    errors = {}
    if request.method == "POST":
        action = request.POST.get("action", "save")
        before = {
            "role": membership.role, "status": membership.status,
            "primary_location": membership.primary_location,
            "additional_locations": membership.additional_locations,
            "specialties": list(membership.specialties.values_list("name", flat=True)),
            "internal_title": membership.internal_title, "internal_notes": membership.internal_notes,
            "working_days": membership.working_days, "working_hours_start": str(membership.working_hours_start or ""),
            "working_hours_end": str(membership.working_hours_end or ""), "time_zone": membership.time_zone,
            "availability": membership.availability,
        }
        if action in {"activate", "deactivate", "suspend", "reactivate"}:
            if membership.user_id == request.user.id:
                errors["access"] = "You cannot change your own access or role."
            if request.POST.get("confirm") != "yes":
                errors["confirm"] = "Confirm this sensitive access change to continue."
            target_status = {
                "activate": StudioMembership.Status.ACTIVE,
                "reactivate": StudioMembership.Status.ACTIVE,
                "deactivate": StudioMembership.Status.INACTIVE,
                "suspend": StudioMembership.Status.SUSPENDED,
            }[action]
            if membership.role == StudioMembership.Role.OWNER and target_status != StudioMembership.Status.ACTIVE:
                errors["owner"] = "Owner access can only be changed through an ownership transfer."
            if not errors:
                membership.status = target_status
                membership.save(update_fields=["status", "updated_at"])
        else:
            role = request.POST.get("role", "")
            availability = request.POST.get("availability", "")
            if role not in StudioMembership.Role.values: errors["role"] = "Choose a valid role."
            if membership.user_id == request.user.id and role != membership.role:
                errors["role"] = "You cannot change your own role."
            if membership.role == StudioMembership.Role.OWNER and role != membership.role:
                errors["role"] = "Transfer ownership before changing the Owner role."
            if role == StudioMembership.Role.OWNER and not actor_access.allows("assign_owner"):
                errors["role"] = "Only an Owner can assign Owner access."
            if role != membership.role and request.POST.get("confirm") != "yes":
                errors["confirm"] = "Confirm this sensitive role change to continue."
            if availability not in StudioMembership.Availability.values: errors["availability"] = "Choose a valid availability."
            start, end = request.POST.get("working_hours_start", ""), request.POST.get("working_hours_end", "")
            if bool(start) != bool(end): errors["working_hours"] = "Enter both a start and end time."
            if start and end and start >= end: errors["working_hours"] = "End time must be later than start time."
            days = [day for day in request.POST.getlist("working_days") if day in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}]
            if not errors:
                membership.role, membership.availability = role, availability
                membership.primary_location = request.POST.get("primary_location", "").strip()[:150]
                membership.additional_locations = [v.strip()[:150] for v in request.POST.get("additional_locations", "").split(",") if v.strip()]
                membership.internal_title = request.POST.get("internal_title", "").strip()[:150]
                membership.internal_notes = request.POST.get("internal_notes", "").strip()[:4000]
                membership.working_days, membership.working_hours_start, membership.working_hours_end = days, start or None, end or None
                membership.time_zone = request.POST.get("time_zone", "").strip()[:64]
                membership.save()
                membership.specialties.set(profile.specialties.model.objects.filter(pk__in=request.POST.getlist("specialties")))
                if membership.user:
                    membership.user.first_name = request.POST.get("first_name", "").strip()[:150]
                    membership.user.last_name = request.POST.get("last_name", "").strip()[:150]
                    membership.user.save(update_fields=["first_name", "last_name", "updated_at"])
        if not errors:
            after = {**before, "role": membership.role, "status": membership.status,
                     "primary_location": membership.primary_location, "additional_locations": membership.additional_locations,
                     "specialties": list(membership.specialties.values_list("name", flat=True)),
                     "internal_title": membership.internal_title, "internal_notes": membership.internal_notes,
                     "working_days": membership.working_days, "working_hours_start": str(membership.working_hours_start or ""),
                     "working_hours_end": str(membership.working_hours_end or ""), "time_zone": membership.time_zone,
                     "availability": membership.availability}
            changes = {key: {"from": before.get(key), "to": value} for key, value in after.items() if before.get(key) != value}
            StudioMembershipEvent.objects.create(membership=membership, actor=request.user, action=action, changes=changes)
            messages.success(request, "Member profile updated.")
            return redirect("photographer_workspace:team_member_detail", pk=membership.pk)
    user = membership.user
    permissions = ROLE_PERMISSIONS[membership.role]
    permission_groups = [
        ("Clients", "clients"), ("Bookings", "bookings"), ("Galleries", "galleries"),
        ("Financial", "financials"), ("Growth", "growth"), ("Analytics", "analytics"),
        ("Team", "team"), ("Settings", "settings"),
    ]
    upcoming_assignments = list(
        ClientSession.objects.for_photographer(profile).filter(
            assigned_members=membership, starts_at__gte=timezone.now(),
        ).exclude(status=ClientSession.Status.CANCELLED).select_related("client").order_by("starts_at")[:6]
    )
    context = _dashboard_context(request, "team_members", "Member Profile")
    context.update({"membership": membership, "member_user": user, "errors": errors,
                    "permission_summary": ACCESS_SUMMARIES[membership.role],
                    "permission_groups": [(label, key in permissions) for label, key in permission_groups],
                    "is_protected_owner": membership.role == StudioMembership.Role.OWNER,
                    "upcoming_assignments": upcoming_assignments,
                    "future_assignment_count": membership.assigned_bookings.filter(starts_at__gte=timezone.now()).count(),
                    "specialty_choices": profile.specialties.model.objects.all().order_by("name"),
                    "selected_specialties": set(membership.specialties.values_list("pk", flat=True)),
                    "day_choices": [("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"), ("thu", "Thursday"),
                                    ("fri", "Friday"), ("sat", "Saturday"), ("sun", "Sunday")],
                    "schedule_url": reverse("photographer_workspace:schedule") + f"?member={membership.pk}"})
    return render(request, "photographer_workspace/team/member_detail.html", context)


@photographer_workspace_required
@require_POST
def invite_member(request):
    profile = authorized_studio(request.user)
    form = InvitationForm(request.POST, studio=profile)
    if not form.is_valid():
        # Do not disclose accounts outside this studio; errors only concern studio membership records.
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("photographer_workspace:team_members")
    with transaction.atomic():
        membership = StudioMembership.objects.create(
            studio=profile, invitation_email=form.cleaned_data["email"],
            invitation_first_name=form.cleaned_data["first_name"].strip(),
            invitation_last_name=form.cleaned_data["last_name"].strip(),
            invitation_phone=form.cleaned_data["phone"].strip(),
            invitation_message=form.cleaned_data["message"].strip(),
            primary_location=form.cleaned_data["primary_location"].strip(),
            role=form.cleaned_data["role"], invited_by=request.user,
        )
        specialty_names = [value.strip() for value in form.cleaned_data["specialties"].split(",") if value.strip()]
        if specialty_names:
            membership.specialties.set(profile.specialties.model.objects.filter(name__in=specialty_names))
        token = issue_token(membership)
        record(membership, request.user, StudioInvitationEvent.Action.SENT)
    try:
        send_invitation(request, membership, token)
    except RuntimeError:
        messages.error(request, "The invitation was saved, but could not be sent. You can resend it below.")
    else:
        messages.success(request, f"Invitation sent to {membership.invitation_email}.")
    return redirect("photographer_workspace:team_members")


@photographer_workspace_required
@require_POST
def invitation_action(request, pk, action):
    profile = authorized_studio(request.user)
    membership = get_object_or_404(StudioMembership, pk=pk, studio=profile,
                                   status=StudioMembership.Status.INVITED)
    if action == "revoke":
        membership.status = StudioMembership.Status.INACTIVE
        membership.invitation_token_digest = ""
        membership.save(update_fields=["status", "invitation_token_digest", "updated_at"])
        record(membership, request.user, StudioInvitationEvent.Action.REVOKED)
        messages.success(request, "Invitation revoked.")
    elif action == "resend":
        if (membership.invitation_sent_at and
                timezone.now() - membership.invitation_sent_at < INVITATION_RESEND_COOLDOWN):
            messages.error(request, "Please wait one minute before resending this invitation.")
            return redirect("photographer_workspace:team_members")
        token = issue_token(membership)
        record(membership, request.user, StudioInvitationEvent.Action.RESENT)
        try:
            send_invitation(request, membership, token)
        except RuntimeError:
            messages.error(request, "The invitation could not be sent. Please try again.")
        else:
            messages.success(request, "Invitation resent with a new secure link and expiration date.")
    else:
        return HttpResponse(status=404)
    return redirect("photographer_workspace:team_members")


@require_http_methods(["GET", "POST"])
def invitation_accept(request, token):
    membership = find_valid_invitation(token)
    if not membership:
        return render(request, "photographer_workspace/team/invitation_invalid.html", status=410)
    invited_email = User.objects.normalize_email(membership.invitation_email).lower()
    if not request.user.is_authenticated:
        return render(request, "photographer_workspace/team/invitation_accept.html", {
            "membership": membership, "role_summary": ROLE_SUMMARIES[membership.role], "token": token,
            "login_url": f'{reverse("accounts:login")}?{urlencode({"next": request.get_full_path()})}',
            "signup_url": f'{reverse("accounts:photographer-signup")}?{urlencode({"next": request.get_full_path()})}',
        })
    email_matches = User.objects.normalize_email(request.user.email).lower() == invited_email
    if request.method == "POST" and email_matches:
        choice = request.POST.get("decision")
        if choice not in {"accept", "decline"}:
            return HttpResponse(status=400)
        with transaction.atomic():
            current = find_valid_invitation(token, lock=True)
            if not current:
                return render(request, "photographer_workspace/team/invitation_invalid.html", status=410)
            current.invitation_token_digest = ""
            if choice == "accept":
                duplicate = StudioMembership.objects.filter(studio=current.studio, user=request.user).exclude(pk=current.pk).exists()
                if duplicate:
                    return render(request, "photographer_workspace/team/invitation_invalid.html", status=409)
                current.user = request.user
                current.status = StudioMembership.Status.ACTIVE
                current.save(update_fields=["user", "status", "invitation_token_digest", "updated_at"])
                record(current, request.user, StudioInvitationEvent.Action.ACCEPTED)
            else:
                current.status = StudioMembership.Status.INACTIVE
                current.save(update_fields=["status", "invitation_token_digest", "updated_at"])
                record(current, request.user, StudioInvitationEvent.Action.DECLINED)
        return render(request, "photographer_workspace/team/invitation_result.html", {"accepted": choice == "accept", "membership": current})
    return render(request, "photographer_workspace/team/invitation_accept.html", {
        "membership": membership, "role_summary": ROLE_SUMMARIES[membership.role], "token": token,
        "email_mismatch": not email_matches,
    })


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
    upcoming_assignments = upcoming_assignments[:5]

    # Membership, assignment, availability, leave, and role-change audit records
    # do not exist yet. Keep the activity timeline empty rather than repurposing
    # CRM or gallery events as team activity.
    activity = []
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
                "severity": "Critical", "tone": "critical", "icon": "bi-calendar2-x",
                "title": "Scheduling conflict",
                "explanation": "This booking overlaps another shoot. No member assignment exists to resolve coverage.",
                "affected": f"{session.session_type} · {session.client}", "timing": timing,
                "action": "Review booking", "url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
            })
        if session.status != ClientSession.Status.COMPLETED:
            alerts.append({
                "severity": "Attention", "tone": "attention", "icon": "bi-person-exclamation",
                "title": "Unassigned upcoming shoot" if session.starts_at >= day_end else "Unassigned shoot",
                "explanation": "No photographer assignment is recorded for this booking.",
                "affected": f"{session.session_type} · {session.client}", "timing": timing,
                "action": "View booking", "url": reverse("photographer_workspace:booking_detail", args=[session.pk]),
            })
    alerts.append({
        "severity": "Information", "tone": "information", "icon": "bi-info-circle",
        "title": "Availability not configured",
        "explanation": "Working hours and time off are not configured, so capacity and leave conflicts cannot be calculated.",
        "affected": owner_name, "timing_label": "Selected day",
        "action": "View members", "url": reverse("photographer_workspace:team_members"),
    })
    kpis = [
        {"label": "Active Team Members", "value": "1", "definition": "Active people with access to this studio workspace.", "status": "Current", "tone": "success", "icon": "bi-people", "available": True},
        {"label": "Available Today", "value": "—", "definition": "Members inside configured working hours with remaining capacity.", "status": "Not configured", "tone": "neutral", "icon": "bi-person-check", "available": False},
        {"label": "On Assignment", "value": "—", "definition": "Members linked to an active shoot on the selected date.", "status": "Data unavailable", "tone": "neutral", "icon": "bi-camera", "available": False},
        {"label": "Unassigned shoots", "value": str(len(day_sessions)), "definition": "Non-cancelled shoots without member-assignment records.", "status": "Needs review" if day_sessions else "Clear", "tone": "warning" if day_sessions else "success", "icon": "bi-exclamation-diamond", "available": True},
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
