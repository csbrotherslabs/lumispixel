from decimal import Decimal
from calendar import Calendar
from datetime import date, datetime, timedelta
import csv
import io
import os
import mimetypes
import zipfile
import secrets
import json
from urllib.parse import urlencode

from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
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
from PIL.Image import DecompressionBombError

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.identity import personal_photo_url
from apps.clients.models import (Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask,
                                Contract, ContractEvent, ContractTemplate, SignedContractDocument,
                                InvoiceActivity, InvoiceCredit, InvoiceLineItem, InvoicePayment, Lead,
                                MiniSession, MiniSessionSlot, MiniSessionSlotBooking, PaymentRefund)
from apps.clients.forms import ClientTaskForm, CrmClientForm, LeadForm
from apps.clients.services import DuplicateClientError, convert_lead_to_client, create_client_note
from apps.billing.services import PlanConfigurationError, get_allowance
from apps.clients.contracts import (DEFAULT_SIGNATURE_CONSENT, ContractDeliveryError, PhotographerSignatureForm,
                                   contract_preview_content, create_contract_from_template,
                                   send_contract_for_review, sign_contract_as_photographer,
                                   validate_contract_for_email)
from apps.galleries.forms import AlbumForm, DiscountCodeForm, GalleryForm, GallerySettingsForm, StoreProductForm, StoreSettingsForm
from apps.galleries.activity import log_gallery_activity
from apps.galleries.storage_cleanup import enqueue_storage_deletions, process_storage_deletions
from apps.galleries.analytics import gallery_analytics_report
from apps.galleries.models import AccessToken, Album, AlbumPhoto, DiscountCode, Gallery, GalleryActivity, GalleryAnalyticsEvent, GalleryArchivePolicy, GalleryInvitation, GalleryMultipartUpload, GalleryOrder, GalleryPermission, GalleryPhoto, GalleryPhotoComment, GalleryPhotoCommentReaction, GalleryStorageDeletion, GallerySettings, GalleryStore, ProductVariant, StoreProduct
from apps.galleries.multipart_uploads import (ALLOWED_CONTENT_TYPES, abort as abort_multipart,
    complete as complete_multipart, delete_object as delete_multipart_object,
    get_object_stream as get_multipart_object_stream, initiate as initiate_multipart,
    multipart_object_key, sign_part, list_parts as list_multipart_parts)
from apps.visual_search.services import schedule_face_indexing
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
from apps.dashboard.contracts import ContractCreateForm, ContractCustomizeForm, ContractTemplateForm
from apps.dashboard.contract_starters import serialized_contract_starters
from apps.clients.contracts import MERGE_FIELDS
from apps.clients.contract_pdfs import generate_signed_contract_pdf
from apps.dashboard.analytics_overview import analytics_overview as build_analytics_overview
from apps.dashboard.scheduling import availability_for, parse_local_datetime, studio_timezone
from apps.dashboard.dashboard_data import build_dashboard
from apps.dashboard.onboarding import build_onboarding
from apps.dashboard.storage_summary import build_storage_summary
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
        if group["title"] == "Galleries" and getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED", False):
            items.append({"key": "private_gallery_requests", "title": "Access requests", "icon": "bi-person-check", "url": reverse("photographer_workspace:private_gallery_requests"), "active": active_key == "private_gallery_requests"})
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
    photo = personal_photo_url(user)
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
        context["onboarding"] = build_onboarding(request.studio_access)
        context["hero_storage"] = build_storage_summary(request.studio_access)
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
    if follow_up == "due":
        leads = leads.filter(next_follow_up__lte=today).exclude(status__in=[Lead.Status.BOOKED, Lead.Status.LOST])
    elif follow_up == "overdue":
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


def _storage_limit_bytes(photographer):
    """Return the authoritative storage limit from the workspace billing plan."""
    allowance = get_allowance(photographer, "storage_bytes")
    if allowance.is_unlimited or allowance.is_custom:
        return None
    if allowance.value is None:
        raise PlanConfigurationError("Numeric storage allowance is missing a value.")
    return allowance.value


def _storage_state(photographer, storage_used):
    limit = _storage_limit_bytes(photographer)
    if limit is None:
        return {
            "limit_bytes": None,
            "available_bytes": None,
            "percent": 0,
            "limit_label": "Custom",
            "available_label": "Custom",
        }
    available = max(limit - storage_used, 0)
    percent = min(round(storage_used / limit * 100), 100) if limit else 100
    return {
        "limit_bytes": limit,
        "available_bytes": available,
        "percent": percent,
        "limit_label": _format_storage(limit),
        "available_label": _format_storage(available),
    }


def _multipart_reserved_bytes(photographer):
    return GalleryMultipartUpload.objects.filter(
        photographer=photographer,
        completed_at__isnull=True,
        aborted_at__isnull=True,
    ).aggregate(
        total=Coalesce(Sum("file_size"), Value(0), output_field=DecimalField())
    )["total"]


def _format_storage(byte_count):
    """Return a compact, presentation-ready storage value."""
    if byte_count >= 1024**3:
        return f"{byte_count / 1024**3:.1f} GB"
    if byte_count >= 1024**2:
        return f"{byte_count / 1024**2:.1f} MB"
    return f"{byte_count / 1024:.1f} KB" if byte_count else "0 GB"


def _gallery_summary(galleries, storage_used, storage_state):
    storage_percent = storage_state["percent"]
    return [
        {"label": "Total Galleries", "value": galleries.count(), "icon": "bi-images", "note": "Across every workflow stage"},
        {"label": "Active Galleries", "value": galleries.exclude(status__in=[Gallery.Status.ARCHIVED, Gallery.Status.EXPIRED, Gallery.Status.DELIVERED]).count(), "icon": "bi-activity", "note": "Currently in your workflow"},
        {"label": "Ready to Deliver", "value": galleries.filter(status=Gallery.Status.READY).count(), "icon": "bi-send-check", "note": "Awaiting your delivery"},
        {"label": "Storage Used", "value": _format_storage(storage_used), "icon": "bi-device-ssd", "note": f"{_format_storage(storage_used)} of {storage_state['limit_label']}", "percent": storage_percent},
    ]


@photographer_workspace_required
@require_GET
def galleries_dashboard(request):
    galleries = _accessible_galleries(request).select_related("client")
    now = timezone.now()
    storage_used = galleries.aggregate(total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField()))["total"]
    storage_state = _storage_state(request.studio, storage_used)
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
    client_activity = _accessible_gallery_activity(request).filter(
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
    if storage_state["limit_bytes"] is not None and storage_state["percent"] >= 80:
        attention.append({"icon": "bi-device-ssd", "title": "Storage is approaching its limit", "description": f"{_format_storage(storage_used)} of {storage_state['limit_label']} is in use.", "url": reverse("photographer_workspace:gallery_upload_queue"), "action": "Manage storage", "tone": "warning"})
    recent_galleries = list(galleries[:6])
    for gallery in recent_galleries:
        gallery.delivery_label = "Delivered" if gallery.status == Gallery.Status.DELIVERED else "Published" if gallery.status == Gallery.Status.PUBLISHED else "Not delivered"
        gallery.badge_variant = "success" if gallery.status in {Gallery.Status.READY, Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED} else "warning" if gallery.status in {Gallery.Status.UPLOADING, Gallery.Status.PROCESSING, Gallery.Status.REVIEW} else "neutral"
    context = _dashboard_context(request, "galleries", "Galleries")
    context.update({
        "has_galleries": galleries.exists(),
        "gallery_summary": _gallery_summary(galleries, storage_used, storage_state), "recent_galleries": recent_galleries,
        "delivery_pipeline": pipeline, "recent_client_activity": activity, "gallery_attention": attention[:5],
        "storage": {"used": _format_storage(storage_used), "available": storage_state["available_label"], "available_bytes": storage_state["available_bytes"], "limit": storage_state["limit_label"], "percent": storage_state["percent"], "percent_display": f"{storage_state['percent']}%"},
        "gallery_deadlines": deadlines,
    })
    return render(request, "photographer_workspace/galleries/dashboard.html", context)


def _accessible_galleries(request):
    """Return galleries visible to this workspace access context."""
    return scope_assigned(Gallery.objects.all(), request.studio_access)


def _accessible_photos(request):
    return GalleryPhoto.objects.filter(gallery__in=_accessible_galleries(request)).distinct()


def _accessible_albums(request):
    return Album.objects.filter(gallery__in=_accessible_galleries(request)).distinct()


def _accessible_gallery_activity(request):
    return GalleryActivity.objects.filter(gallery__in=_accessible_galleries(request)).distinct()


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
    galleries = _accessible_galleries(request).order_by("name")
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

    jobs = AIJob.objects.for_photographer(profile).filter(gallery__in=_accessible_galleries(request)).select_related("gallery", "gallery__client", "progress")
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
    job = get_object_or_404(AIJob.objects.for_photographer(request.studio).filter(gallery__in=_accessible_galleries(request)), pk=pk)
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
    card_photos = _accessible_photos(request).filter(
        is_visible=True, status=GalleryPhoto.Status.COMPLETED
    ).order_by("-is_cover", "-created_at")
    all_records = _accessible_galleries(request).active().select_related("client").prefetch_related(
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
    records = _accessible_galleries(request).archived().select_related("client", "archived_by")
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
    all_archived = _accessible_galleries(request).archived()
    policy, _ = GalleryArchivePolicy.objects.get_or_create(photographer=profile)
    context = _dashboard_context(request, "gallery_archive", "Gallery Archive")
    context.update({
        "archive_page": page, "archive_query": query, "selected_reason": reason, "selected_retention": retention,
        "selected_date_from": date_from, "selected_date_to": date_to, "selected_storage": storage, "selected_sort": sort,
        "archive_reasons": Gallery.ArchiveReason.choices, "retention_choices": Gallery.RetentionType.choices,
        "active_galleries": _accessible_galleries(request).active().order_by("name"), "policy": policy,
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
    records = _accessible_galleries(request).filter(pk__in=ids, deleted_at__isnull=True)
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
            deletion_items = [
                {
                    "storage_backend": "b2" if settings.GALLERY_STORAGE_BACKEND == "b2" else "default",
                    "object_key": photo.file.name,
                    "photographer_id": photo.photographer_id,
                    "gallery_id": gallery.pk,
                }
                for photo in gallery.photos.all() if photo.file
            ]
            with transaction.atomic():
                enqueue_storage_deletions(deletion_items)
                gallery.deleted_at = now
                gallery.save(update_fields=["deleted_at", "updated_at"])
                gallery.delete()
            process_storage_deletions()
            messages.success(request, "Gallery and associated non-financial records permanently deleted.")
    return redirect("photographer_workspace:gallery_archive")


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def create_gallery(request):
    profile = request.studio
    initial = {}
    requested_design = request.GET.get("design")
    valid_designs = {choice.value for choice in Gallery.DesignTemplate}
    if request.method == "GET" and requested_design in valid_designs:
        initial["design_template"] = requested_design
    form = GalleryForm(request.POST or None, request.FILES or None, photographer=profile, initial=initial)
    form.fields["description"].widget.attrs["rows"] = 3
    form.fields["cover_image"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
    form.fields["name"].widget.attrs["placeholder"] = "e.g. Maya & Rowan"
    if request.method == "POST" and form.is_valid():
        gallery = form.save(commit=False)
        gallery.photographer = profile
        gallery.slug = _unique_gallery_slug(profile, gallery.name)
        gallery.full_clean()
        gallery.save()
        # Semantic authorization is separate and gated; facial search remains off.
        if request.POST.get("semantic_search_enabled") == "on":
            from apps.visual_search.models import GallerySemanticSearchPolicy
            from apps.visual_search.semantic import semantic_enabled
            if semantic_enabled() and getattr(settings, "VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED", False):
                GallerySemanticSearchPolicy.objects.update_or_create(
                    gallery=gallery, defaults={"processing_authorized": True}
                )
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
    context["semantic_create_available"] = bool(getattr(settings, "VISUAL_SEARCH_SEMANTIC_ENABLED", False) and getattr(settings, "VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED", False))
    context.update({"form": form, "form_title": "Create Gallery", "form_subtitle": "Set up the gallery now. Add photos and delivery settings next.", "submit_label": "Create Gallery", "is_create_gallery": True, "hide_topbar_heading": True})
    return render(request, "photographer_workspace/galleries/form.html", context)


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def edit_gallery(request, pk):
    profile = request.studio
    gallery = get_object_or_404(_accessible_galleries(request), pk=pk)
    form = GalleryForm(request.POST or None, request.FILES or None, instance=gallery, photographer=profile)
    if request.method == "POST" and form.is_valid():
        previous = {"name": gallery.name, "status": gallery.status, "visibility": gallery.visibility, "design_template": gallery.design_template}
        gallery = form.save(commit=False)
        gallery.slug = _unique_gallery_slug(profile, gallery.name, gallery.pk)
        gallery.full_clean()
        gallery.save()
        log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.GALLERY_UPDATED,
                             description="Gallery details were updated.", actor=request.user,
                             metadata={"previous_value": previous, "new_value": {"name": gallery.name, "status": gallery.status, "visibility": gallery.visibility, "design_template": gallery.design_template}})
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
    records = _accessible_galleries(request).filter(pk__in=ids)
    action = request.POST.get("action")
    if not ids:
        messages.error(request, "Select at least one gallery.")
    elif action == "delete":
        galleries = list(records.prefetch_related("photos"))
        count = len(galleries)
        deletion_items = []
        backend = (
            GalleryStorageDeletion.Backend.B2
            if settings.GALLERY_STORAGE_BACKEND == "b2"
            else GalleryStorageDeletion.Backend.DEFAULT
        )
        for gallery in galleries:
            for photo in gallery.photos.all():
                if photo.file and photo.file.name:
                    deletion_items.append({
                        "storage_backend": backend,
                        "object_key": photo.file.name,
                        "photographer_id": profile.pk,
                        "gallery_id": gallery.pk,
                    })
        with transaction.atomic():
            enqueue_storage_deletions(deletion_items)
            Gallery.objects.filter(pk__in=[gallery.pk for gallery in galleries]).delete()
        process_storage_deletions()
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



MAX_IMAGE_PIXELS = int(os.getenv("MAX_GALLERY_IMAGE_PIXELS", "100000000"))


def _validate_image_bytes(content, expected_content_type):
    """Verify decoded image bytes and require the detected format to match declared MIME."""
    expected_formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    expected_format = expected_formats.get(expected_content_type)
    if not expected_format:
        return False
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != expected_format:
                return False
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                return False
            image.verify()
        return True
    except (DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        return False


def _validate_image_file(file_obj, expected_content_type, *, expected_size=None):
    """Validate an image from a seekable file/stream without copying it into a bytes object."""
    expected_formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    expected_format = expected_formats.get(expected_content_type)
    if not expected_format:
        return False
    try:
        if expected_size is not None:
            file_obj.seek(0, 2)
            if file_obj.tell() != expected_size:
                return False
            file_obj.seek(0)
        with Image.open(file_obj) as image:
            if image.format != expected_format:
                return False
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                return False
            image.verify()
        return True
    except (DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        return False


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _multipart_session(request, upload_uuid):
    return get_object_or_404(
        GalleryMultipartUpload.objects.select_related("gallery").filter(
            gallery__in=_accessible_galleries(request)
        ),
        pk=upload_uuid,
        photographer=request.studio,
    )


@photographer_workspace_required
@require_POST
def gallery_multipart_initiate(request):
    data = _json_body(request)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    gallery = get_object_or_404(_accessible_galleries(request), pk=data.get("gallery"))
    name = str(data.get("name") or "")[:255]
    content_type = str(data.get("content_type") or "")
    try:
        size = int(data.get("size"))
    except (TypeError, ValueError):
        size = 0
    if not name or content_type not in ALLOWED_CONTENT_TYPES or size <= 0 or size > settings.MAX_GALLERY_UPLOAD_BYTES:
        return JsonResponse({"error": "Use a JPG, PNG, or WebP image within the configured upload limit."}, status=400)
    storage_used = Gallery.objects.for_photographer(request.studio).aggregate(
        total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField())
    )["total"]
    reserved = _multipart_reserved_bytes(request.studio)
    storage_limit = _storage_limit_bytes(request.studio)
    if storage_limit is not None and size > max(storage_limit - storage_used - reserved, 0):
        return JsonResponse({"error": "Not enough storage to upload this file."}, status=400)
    key = multipart_object_key(
        photographer_id=request.studio.pk, gallery_id=gallery.pk,
        original_name=name, content_type=content_type,
    )
    try:
        upload_id = initiate_multipart(key=key, content_type=content_type)
    except Exception:
        return JsonResponse({"error": "Could not start direct upload."}, status=502)
    try:
        session = GalleryMultipartUpload.objects.create(
            gallery=gallery, photographer=request.studio, object_key=key, upload_id=upload_id,
            original_name=name, content_type=content_type, file_size=size,
        )
    except Exception:
        # B2 accepted the multipart upload but Django could not persist its
        # recovery record. Abort immediately so the provider cannot retain an
        # untracked multipart upload.
        try:
            abort_multipart(key=key, upload_id=upload_id)
        except Exception:
            pass
        return JsonResponse({"error": "Could not persist direct upload state."}, status=500)
    return JsonResponse({
        "upload": str(session.pk), "part_size": settings.B2_MULTIPART_MIN_PART_BYTES,
        "max_parts": settings.B2_MULTIPART_MAX_PARTS,
    }, status=201)


@photographer_workspace_required
@require_POST
def gallery_multipart_resume(request, upload_uuid):
    session = _multipart_session(request, upload_uuid)
    if session.completed_at or session.aborted_at:
        return JsonResponse({"error": "Upload is no longer active."}, status=409)
    try:
        parts = list_multipart_parts(key=session.object_key, upload_id=session.upload_id)
    except Exception:
        return JsonResponse({"error": "Could not inspect direct upload."}, status=502)
    return JsonResponse({
        "upload": str(session.pk),
        "gallery": session.gallery_id,
        "name": session.original_name,
        "content_type": session.content_type,
        "size": session.file_size,
        "part_size": settings.B2_MULTIPART_MIN_PART_BYTES,
        "max_parts": settings.B2_MULTIPART_MAX_PARTS,
        "parts": parts,
    })


@photographer_workspace_required
@require_POST
def gallery_multipart_sign_part(request, upload_uuid):
    session = _multipart_session(request, upload_uuid)
    if session.completed_at:
        photo = GalleryPhoto.objects.filter(multipart_upload=session).first()
        if photo:
            return JsonResponse({"photo": {"id": photo.pk, "name": photo.original_name, "size": photo.file_size, "status": photo.status}, "idempotent": True}, status=200)
        return JsonResponse({"error": "Upload completion state is inconsistent."}, status=409)
    if session.aborted_at:
        return JsonResponse({"error": "Upload is no longer active."}, status=409)
    data = _json_body(request)
    try:
        part_number = int((data or {}).get("part_number"))
    except (TypeError, ValueError):
        part_number = 0
    if not 1 <= part_number <= settings.B2_MULTIPART_MAX_PARTS:
        return JsonResponse({"error": "Invalid part number."}, status=400)
    try:
        url = sign_part(key=session.object_key, upload_id=session.upload_id, part_number=part_number)
    except Exception:
        return JsonResponse({"error": "Could not authorize upload part."}, status=502)
    return JsonResponse({"part_number": part_number, "url": url})


@photographer_workspace_required
@require_POST
def gallery_multipart_complete(request, upload_uuid):
    session = _multipart_session(request, upload_uuid)
    if session.completed_at:
        photo = GalleryPhoto.objects.filter(multipart_upload=session).first()
        if photo:
            return JsonResponse({"photo": {"id": photo.pk, "name": photo.original_name, "size": photo.file_size, "status": photo.status}, "idempotent": True}, status=200)
        return JsonResponse({"error": "Upload completion state is inconsistent."}, status=409)
    if session.aborted_at:
        return JsonResponse({"error": "Upload is no longer active."}, status=409)
    data = _json_body(request)
    parts = (data or {}).get("parts")
    if not isinstance(parts, list) or not parts:
        return JsonResponse({"error": "Completed parts are required."}, status=400)
    normalized = []
    try:
        for item in parts:
            normalized.append({"PartNumber": int(item["part_number"]), "ETag": str(item["etag"])})
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "Invalid completed parts."}, status=400)
    numbers = [item["PartNumber"] for item in normalized]
    if numbers != sorted(set(numbers)) or numbers[0] != 1 or numbers[-1] > settings.B2_MULTIPART_MAX_PARTS:
        return JsonResponse({"error": "Parts must be unique and ordered from part 1."}, status=400)
    try:
        complete_multipart(key=session.object_key, upload_id=session.upload_id, parts=normalized)
    except Exception:
        return JsonResponse({"error": "Could not complete direct upload."}, status=502)
    try:
        object_stream = get_multipart_object_stream(key=session.object_key)
        try:
            valid_image = _validate_image_file(object_stream, session.content_type, expected_size=session.file_size)
        finally:
            object_stream.close()
    except Exception:
        try:
            delete_multipart_object(key=session.object_key)
        except Exception:
            pass
        session.aborted_at = timezone.now()
        session.save(update_fields=["aborted_at"])
        return JsonResponse({"error": "Could not validate the uploaded image."}, status=502)
    if not valid_image:
        try:
            delete_multipart_object(key=session.object_key)
        except Exception:
            pass
        session.aborted_at = timezone.now()
        session.save(update_fields=["aborted_at"])
        return JsonResponse({"error": "The uploaded file is not a valid image."}, status=400)
    expected_prefix = (
        f"private/{settings.GALLERY_STORAGE_ENVIRONMENT}/galleries/"
        f"{request.studio.pk}/{session.gallery_id}/originals/"
    )
    object_name = session.object_key[len(expected_prefix):] if session.object_key.startswith(expected_prefix) else ""
    if (
        not object_name
        or "/" in object_name
        or "\\\\" in object_name
        or object_name in {".", ".."}
        or not object_name.endswith(ALLOWED_CONTENT_TYPES[session.content_type])
    ):
        try:
            delete_multipart_object(key=session.object_key)
        except Exception:
            pass
        session.aborted_at = timezone.now()
        session.save(update_fields=["aborted_at"])
        return JsonResponse({"error": "Invalid object key."}, status=400)
    relative_name = session.object_key[len(f"private/{settings.GALLERY_STORAGE_ENVIRONMENT}/"): ]
    with transaction.atomic():
        # Re-read and lock the upload state after the provider completion call.
        # A retry or concurrent completion must not create a second photo or
        # increment gallery accounting twice.
        locked_session = GalleryMultipartUpload.objects.select_for_update().get(pk=session.pk)
        if locked_session.completed_at:
            photo = GalleryPhoto.objects.filter(multipart_upload=locked_session).first()
            if photo:
                return JsonResponse({"photo": {"id": photo.pk, "name": photo.original_name, "size": photo.file_size, "status": photo.status}, "idempotent": True}, status=200)
            return JsonResponse({"error": "Upload completion state is inconsistent."}, status=409)
        if locked_session.aborted_at:
            return JsonResponse({"error": "Upload is no longer active."}, status=409)
        photo = GalleryPhoto.objects.create(
            gallery=locked_session.gallery, photographer=request.studio, multipart_upload=locked_session, file=relative_name,
            original_name=locked_session.original_name, file_size=locked_session.file_size,
            status=GalleryPhoto.Status.COMPLETED,
        )
        schedule_face_indexing(photo.pk)
        Gallery.objects.filter(pk=locked_session.gallery_id).update(
            image_count=F("image_count") + 1, storage_used=F("storage_used") + locked_session.file_size
        )
        locked_session.completed_at = timezone.now()
        locked_session.save(update_fields=["completed_at"])
        log_gallery_activity(
            gallery=locked_session.gallery, event_type=GalleryActivity.EventType.PHOTOS_UPLOADED,
            description="1 photo uploaded successfully via direct multipart upload.",
            actor=request.user, metadata={"count": 1, "files": [locked_session.original_name]},
        )
    return JsonResponse({"photo": {"id": photo.pk, "name": photo.original_name, "size": photo.file_size, "status": photo.status}}, status=201)


@photographer_workspace_required
@require_POST
def gallery_multipart_abort(request, upload_uuid):
    session = _multipart_session(request, upload_uuid)
    if session.completed_at:
        return JsonResponse({"error": "Completed uploads cannot be aborted."}, status=409)
    if not session.aborted_at:
        try:
            abort_multipart(key=session.object_key, upload_id=session.upload_id)
        except Exception:
            return JsonResponse({"error": "Could not abort direct upload."}, status=502)
        session.aborted_at = timezone.now()
        session.save(update_fields=["aborted_at"])
    return JsonResponse({"aborted": True})


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def gallery_upload_queue(request):
    profile = request.studio
    galleries = _accessible_galleries(request).select_related("client")
    if request.method == "POST":
        gallery = get_object_or_404(galleries, pk=request.POST.get("gallery"))
        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"error": "Choose at least one image."}, status=400)
        created, errors = [], []
        allowed = set(ALLOWED_CONTENT_TYPES)
        max_size = settings.MAX_GALLERY_UPLOAD_BYTES
        storage_used = galleries.aggregate(
            total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField())
        )["total"]
        storage_limit = _storage_limit_bytes(profile)
        reserved = _multipart_reserved_bytes(profile)
        storage_remaining = None if storage_limit is None else max(storage_limit - storage_used - reserved, 0)
        for upload in files:
            if upload.content_type not in allowed or upload.size > max_size:
                errors.append({"name": upload.name, "error": "Use a JPG, PNG, or WebP image within the configured upload limit."})
                continue
            if storage_remaining is not None and upload.size > storage_remaining:
                errors.append({"name": upload.name, "error": "Not enough storage to upload these files."})
                continue
            try:
                valid_image = _validate_image_file(upload, upload.content_type, expected_size=upload.size)
                upload.seek(0)
            except OSError:
                valid_image = False
            if not valid_image:
                errors.append({"name": upload.name, "error": "The file is not a valid image."})
                continue
            photo = GalleryPhoto(gallery=gallery, photographer=profile, file=upload, original_name=upload.name[:255], file_size=upload.size, status=GalleryPhoto.Status.COMPLETED)
            try:
                photo.full_clean()
                photo.save()
            except Exception:
                errors.append({"name": upload.name, "error": "The image could not be validated."})
                continue
            schedule_face_indexing(photo.pk)
            created.append({"id": photo.pk, "name": photo.original_name, "size": photo.file_size, "status": photo.status})
            if storage_remaining is not None:
                storage_remaining -= upload.size
        if created:
            Gallery.objects.filter(pk=gallery.pk).update(image_count=F("image_count") + len(created), storage_used=F("storage_used") + sum(item["size"] for item in created))
            log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.PHOTOS_UPLOADED,
                                 description=f"{len(created)} photo{'s' if len(created) != 1 else ''} uploaded successfully.", actor=request.user,
                                 metadata={"count": len(created), "files": [item["name"] for item in created[:10]]})
        return JsonResponse({"uploads": created, "errors": errors}, status=201 if created else 400)
    upload_records = _accessible_photos(request)
    visible_upload_records = upload_records.filter(upload_queue_dismissed=False)
    counts = {status: visible_upload_records.filter(status=status).count() for status in GalleryPhoto.Status.values}
    uploads = visible_upload_records.select_related("gallery")[:100]
    storage_used = galleries.aggregate(total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField()))["total"]
    storage_state = _storage_state(profile, storage_used)
    storage_percent = storage_state["percent"]
    selected_gallery = galleries.filter(pk=request.GET.get("gallery")).first() if request.GET.get("gallery") else None
    context = _dashboard_context(request, "gallery_upload_queue", "Upload Queue")
    context.update({"gallery_choices": galleries, "uploads": uploads, "upload_counts": counts,
                    "selected_gallery": selected_gallery,
                    "max_upload_bytes": settings.MAX_GALLERY_UPLOAD_BYTES,
                    "max_upload_mb": settings.MAX_GALLERY_UPLOAD_BYTES / 1024**2,
                    "storage": {"used": _format_storage(storage_used),
                                "available": storage_state["available_label"],
                                "available_bytes": storage_state["available_bytes"],
                                "limit": storage_state["limit_label"],
                                "percent": storage_percent}})
    return render(request, "photographer_workspace/galleries/upload_queue.html", context)


@photographer_workspace_required
@require_POST
def gallery_upload_queue_clear_completed(request):
    updated = _accessible_photos(request).filter(
        status=GalleryPhoto.Status.COMPLETED,
        upload_queue_dismissed=False,
    ).update(upload_queue_dismissed=True)
    return JsonResponse({"ok": True, "dismissed": updated})

@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def gallery_workspace(request, pk):
    gallery = get_object_or_404(
        _accessible_galleries(request).select_related("client"), pk=pk
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
        if action == "publish_gallery":
            if gallery.status in {Gallery.Status.ARCHIVED, Gallery.Status.EXPIRED}:
                messages.error(request, "Restore this gallery before publishing it.")
            else:
                was_published = gallery.status == Gallery.Status.PUBLISHED
                gallery.status = Gallery.Status.PUBLISHED
                if not gallery.published_at:
                    gallery.published_at = timezone.now()
                gallery.save(update_fields=["status", "published_at", "updated_at"])
                if not was_published:
                    log_gallery_activity(
                        gallery=gallery,
                        event_type=GalleryActivity.EventType.GALLERY_PUBLISHED,
                        title="Gallery published",
                        description="Gallery published from its workspace.",
                        actor=request.user,
                    )
                messages.success(request, "Gallery published and ready for client access.")
            return redirect("photographer_workspace:gallery_workspace", pk=gallery.pk)
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
            try:
                density = int(request.POST.get("watermark_density", permissions.watermark_density))
            except (ValueError, TypeError):
                return HttpResponseBadRequest("Choose a watermark density from 1 to 5.")
            if not 1 <= density <= 5:
                return HttpResponseBadRequest("Choose a watermark density from 1 to 5.")
            permissions.watermark_density = density
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
                                 related_object=permissions, metadata={"new_value": {"visibility": gallery.visibility, "watermark": permissions.watermark, "watermark_density": permissions.watermark_density}})
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
        elif action in {"resend", "disable",…48421 tokens truncated…                errors["owner"] = "Owner access can only be changed through an ownership transfer."
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
