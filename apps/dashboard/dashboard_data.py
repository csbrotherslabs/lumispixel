"""Server-side preparation for the photographer workspace dashboard.

Every queryset starts from the authorized studio and assignment scope. Templates
receive display-ready values and never calculate business metrics.
"""
from calendar import month_abbr
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientActivity, ClientInvoice, ClientSession, InvoicePayment, Lead
from apps.dashboard.access import scope_assigned
from apps.galleries.models import Gallery, GalleryActivity

MONEY = DecimalField(max_digits=14, decimal_places=2)
OPEN_GALLERY_STATES = [Gallery.Status.DRAFT, Gallery.Status.UPLOADING, Gallery.Status.PROCESSING,
                       Gallery.Status.REVIEW, Gallery.Status.READY, Gallery.Status.PUBLISHED]


def _money(currency, amount):
    return f"{currency} {amount:,.2f}"


def _month_bounds(day):
    start = day.replace(day=1)
    previous_end = start - timedelta(days=1)
    return start, previous_end.replace(day=1), previous_end


def _sessions(access):
    return scope_assigned(ClientSession.objects.select_related("client"), access)


def _galleries(access):
    return scope_assigned(Gallery.objects.select_related("client").active(), access)


def build_dashboard(access, *, now=None):
    """Return honest, display-ready dashboard data for one authorized workspace."""
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    month_start, previous_start, previous_end = _month_bounds(today)
    financial = access.allows("financials")
    sessions = _sessions(access)
    galleries = _galleries(access)

    upcoming = sessions.filter(starts_at__gte=now).exclude(status=ClientSession.Status.CANCELLED)
    today_sessions = upcoming.filter(starts_at__date=today)
    queue = galleries.filter(status__in=OPEN_GALLERY_STATES)

    revenue = previous_revenue = None
    outstanding = None
    overdue_invoices = 0
    if financial:
        payments = InvoicePayment.objects.filter(photographer=access.studio, status=InvoicePayment.Status.COMPLETED)
        revenue = payments.filter(paid_at__date__gte=month_start).aggregate(
            value=Coalesce(Sum("amount"), Value(Decimal("0")), output_field=MONEY))["value"]
        previous_revenue = payments.filter(paid_at__date__range=(previous_start, previous_end)).aggregate(
            value=Coalesce(Sum("amount"), Value(Decimal("0")), output_field=MONEY))["value"]
        balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY)
        open_invoices = ClientInvoice.objects.filter(photographer=access.studio).exclude(
            status__in=[ClientInvoice.Status.PAID, ClientInvoice.Status.VOID, ClientInvoice.Status.DRAFT]).annotate(balance=balance)
        outstanding = open_invoices.aggregate(value=Coalesce(Sum("balance"), Value(Decimal("0")), output_field=MONEY))["value"]
        overdue_invoices = open_invoices.filter(due_date__lt=today, balance__gt=0).count()

    current_bookings = sessions.filter(starts_at__date__gte=month_start, starts_at__date__lte=today).exclude(status=ClientSession.Status.CANCELLED).count()
    previous_bookings = sessions.filter(starts_at__date__range=(previous_start, previous_end)).exclude(status=ClientSession.Status.CANCELLED).count()
    awaiting = queue.count()

    def comparison(current, previous, noun=""):
        if previous == 0:
            return None
        delta = current - previous
        return {"change": f"{abs(delta):,} {noun}".strip(), "trend": "increase" if delta > 0 else "decrease" if delta < 0 else "neutral",
                "comparison": "more than last month" if delta > 0 else "fewer than last month" if delta < 0 else "same as last month"}

    kpis = []
    if financial:
        rev_compare = None
        if previous_revenue:
            pct = ((revenue - previous_revenue) / previous_revenue * 100).quantize(Decimal("1"))
            rev_compare = {"change": f"{abs(pct)}%", "trend": "increase" if pct > 0 else "decrease" if pct < 0 else "neutral", "comparison": "from last month"}
        kpis.append({"label": "Revenue this month", "icon": "bi-cash-stack", "value": _money(access.studio.default_currency, revenue), "context": "Completed invoice payments", **(rev_compare or {})})
    else:
        kpis.append({"label": "Revenue this month", "icon": "bi-cash-stack", "unavailable": True, "context": "Financial access is required"})
    kpis.extend([
        {"label": "Upcoming bookings", "icon": "bi-calendar2-check", "value": upcoming.count(), "context": "Future tentative and confirmed sessions", **(comparison(current_bookings, previous_bookings, "bookings") or {})},
        {"label": "Galleries awaiting delivery", "icon": "bi-images", "value": awaiting, "context": "Active workflow stages; no delivery deadline is stored"},
        {"label": "Outstanding payments", "icon": "bi-receipt", "value": _money(access.studio.default_currency, outstanding) if financial else None,
         "unavailable": not financial, "context": "Sent and partially paid invoice balances" if financial else "Financial access is required"},
    ])

    attentions = []
    if overdue_invoices:
        attentions.append({"icon": "bi-receipt", "title": f"{overdue_invoices} overdue invoice{'s' if overdue_invoices != 1 else ''}", "url": reverse("photographer_workspace:invoices")})
    failed_galleries = galleries.filter(status__in=[Gallery.Status.UPLOADING, Gallery.Status.PROCESSING]).filter(updated_at__lt=now-timedelta(days=1)).count()
    if failed_galleries:
        attentions.append({"icon": "bi-cloud-exclamation", "title": f"{failed_galleries} upload or processing job{'s' if failed_galleries != 1 else ''} may need review", "url": reverse("photographer_workspace:gallery_upload_queue")})
    if access.role != "photographer":
        unanswered = Lead.objects.for_photographer(access.studio).filter(status=Lead.Status.NEW, last_contacted_at__isnull=True).count()
        if unanswered:
            attentions.append({"icon": "bi-reply", "title": f"{unanswered} new lead{'s' if unanswered != 1 else ''} awaiting a response", "url": reverse("photographer_workspace:leads")})

    schedule = [{"date": item.starts_at, "client": str(item.client), "type": item.session_type,
                 "location": item.location or "Location not set", "status": item.get_status_display(),
                 "url": reverse("photographer_workspace:booking_detail", args=[item.pk])}
                for item in upcoming[:5]]
    gallery_queue = [{"name": item.name, "client": str(item.client) if item.client else "No client linked",
                      "stage": item.get_status_display(), "due": None, "progress": None,
                      "risk": "Deadline unavailable", "url": reverse("photographer_workspace:gallery_workspace", args=[item.pk])}
                     for item in queue.order_by("updated_at")[:5]]

    activity = []
    client_events = ClientActivity.objects.filter(photographer=access.studio).select_related("client", "lead")
    gallery_events = GalleryActivity.objects.filter(photographer=access.studio).select_related("gallery")
    if access.role == "photographer":
        assigned_client_ids = scope_assigned(Client.objects.all(), access).values("pk")
        client_events = client_events.filter(client_id__in=assigned_client_ids)
        gallery_events = gallery_events.filter(gallery_id__in=galleries.values("pk"))
    client_events = client_events[:6]
    gallery_events = gallery_events[:6]
    for event in client_events:
        activity.append({"description": event.get_event_type_display(), "entity": str(event.client or event.lead or ""), "at": event.occurred_at,
                         "url": reverse("photographer_workspace:client_detail", args=[event.client_id]) if event.client_id else reverse("photographer_workspace:leads")})
    for event in gallery_events:
        activity.append({"description": event.title, "entity": event.gallery.name, "at": event.created_at,
                         "url": reverse("photographer_workspace:gallery_workspace", args=[event.gallery_id])})
    activity = sorted(activity, key=lambda item: item["at"], reverse=True)[:6]

    chart = []
    for offset in range(5, -1, -1):
        year = today.year + (today.month - 1 - offset) // 12
        month = (today.month - 1 - offset) % 12 + 1
        count = sessions.filter(starts_at__year=year, starts_at__month=month).exclude(status=ClientSession.Status.CANCELLED).count()
        amount = None
        if financial:
            amount = payments.filter(paid_at__year=year, paid_at__month=month).aggregate(value=Coalesce(Sum("amount"), Value(Decimal("0")), output_field=MONEY))["value"]
        chart.append({"label": month_abbr[month], "bookings": count, "revenue": amount})
    max_bookings = max([point["bookings"] for point in chart] or [0])
    max_revenue = max([point["revenue"] or 0 for point in chart] or [0])
    for point in chart:
        point["booking_height"] = max(4, round(point["bookings"] / max_bookings * 100)) if max_bookings else 0
        point["revenue_height"] = max(4, round(point["revenue"] / max_revenue * 100)) if max_revenue and point["revenue"] else 0

    storage = galleries.aggregate(total=Coalesce(Sum("storage_used"), Value(0)))["total"]
    most_booked = sessions.exclude(status=ClientSession.Status.CANCELLED).values("session_type").annotate(total=Count("id")).order_by("-total", "session_type").first()
    insight = None
    if most_booked and most_booked["total"] >= 2:
        insight = {"label": "Business Insight", "title": f"{most_booked['session_type']} is your most-booked service",
                   "body": f"It appears in {most_booked['total']} saved bookings. Use this pattern when planning availability and packages."}

    summary_parts = []
    if today_sessions.count(): summary_parts.append(f"{today_sessions.count()} session{'s' if today_sessions.count() != 1 else ''} today")
    if awaiting: summary_parts.append(f"{awaiting} galler{'ies' if awaiting != 1 else 'y'} awaiting delivery")
    day_summary = "You have " + " and ".join(summary_parts) + "." if summary_parts else "Your schedule is clear; review the next steps to keep your workspace moving."
    return {"today": today, "day_summary": day_summary, "attention_items": attentions[:3], "attention_total": len(attentions),
            "kpis": kpis, "schedule_items": schedule, "gallery_queue": gallery_queue, "activity_items": activity,
            "performance_chart": chart, "can_view_financials": financial, "storage_bytes": storage, "insight": insight,
            "has_business_data": sessions.exists() or galleries.exists() or (financial and bool(revenue or outstanding))}
