"""Read-only, cross-product analytics assembled from LumisPixel source records."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from apps.clients.models import Client, ClientSession, InvoiceLineItem, InvoicePayment, Lead, PaymentRefund
from apps.galleries.models import Gallery, GalleryAnalyticsEvent


RANGES = (("30_days", "Last 30 days"), ("this_month", "This month"),
          ("this_quarter", "This quarter"), ("this_year", "This year"), ("custom", "Custom range"))
COMPARES = (("previous_period", "Previous period"), ("previous_year", "Previous year"), ("none", "No comparison"))


def _window(params, today):
    key = params.get("range", "30_days")
    if key == "custom":
        try:
            start, end = (datetime.strptime(params.get(name, ""), "%Y-%m-%d").date() for name in ("start", "end"))
            if start > end:
                raise ValueError
            return key, start, end
        except ValueError:
            key = "30_days"
    if key == "this_month": start = today.replace(day=1)
    elif key == "this_quarter": start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
    elif key == "this_year": start = today.replace(month=1, day=1)
    else: start = today - timedelta(days=29)
    return key, start, today


def _comparison(key, start, end):
    if key == "none": return None, None
    if key == "previous_year":
        try: return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
        except ValueError: return start - timedelta(days=365), end - timedelta(days=365)
    length = end - start + timedelta(days=1)
    return start - length, start - timedelta(days=1)


def _money(value, currency):
    symbols = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "CA$", "AUD": "A$"}
    return f"{symbols.get(currency, currency + ' ')}{value:,.0f}"


def _metric(label, value, previous, display, icon, tooltip, url, compare_label, spark):
    if previous is None:
        change, tone, direction, note = "Not compared", "neutral", "neutral", "Comparison is turned off"
    elif not previous:
        change, tone, direction, note = "No prior data", "neutral", "neutral", f"No data in {compare_label.lower()}"
    else:
        delta = (Decimal(str(value)) - Decimal(str(previous))) / Decimal(str(previous)) * 100
        direction = "up" if delta > 0 else "down" if delta < 0 else "neutral"
        tone = "positive" if delta > 0 else "negative" if delta < 0 else "neutral"
        change, note = f"{delta:+.1f}%", f"vs {compare_label.lower()}"
    heights = [max(8, min(100, int((Decimal(str(point)) / max([Decimal(str(x)) for x in spark] + [Decimal('1')])) * 100))) for point in spark]
    return {"label": label, "raw": value, "value": display(value), "change": change, "tone": tone,
            "direction": direction, "icon": icon, "note": note, "tooltip": tooltip, "url": url, "spark": heights}


def analytics_overview(profile, params, base_url, today=None):
    """Return filter choices and KPI values; every query remains owner scoped."""
    today = today or timezone.localdate()
    range_key, start, end = _window(params, today)
    compare_key = params.get("compare", "previous_period")
    if compare_key not in dict(COMPARES): compare_key = "previous_period"
    previous_start, previous_end = _comparison(compare_key, start, end)
    selected = {key: params.get(key, "").strip() for key in
                ("location", "member", "service", "package", "lead_source", "client_type", "booking_status", "gallery_status")}

    sessions = ClientSession.objects.for_photographer(profile).select_related("client")
    leads = Lead.objects.for_photographer(profile)
    clients = Client.objects.for_photographer(profile)
    galleries = Gallery.objects.for_photographer(profile)
    events = GalleryAnalyticsEvent.objects.for_photographer(profile)
    if selected["location"]: sessions = sessions.filter(location=selected["location"])
    if selected["service"]: sessions = sessions.filter(session_type=selected["service"])
    if selected["booking_status"]: sessions = sessions.filter(status=selected["booking_status"])
    if selected["client_type"]:
        sessions, clients = sessions.filter(client__client_type=selected["client_type"]), clients.filter(client_type=selected["client_type"])
    if selected["lead_source"]:
        leads = leads.filter(lead_source=selected["lead_source"])
        clients = clients.filter(converted_lead__lead_source=selected["lead_source"])
        sessions = sessions.filter(client__converted_lead__lead_source=selected["lead_source"])
    if selected["package"]:
        booking_ids = InvoiceLineItem.objects.filter(item_type=InvoiceLineItem.ItemType.PACKAGE,
            description=selected["package"], invoice__photographer=profile).values("invoice__booking_id")
        sessions = sessions.filter(pk__in=booking_ids)
    if selected["gallery_status"]:
        galleries = galleries.filter(status=selected["gallery_status"])
        events = events.filter(gallery__status=selected["gallery_status"])

    def period(qs, field, a, b): return qs.filter(**{f"{field}__date__gte": a, f"{field}__date__lte": b})
    booked = sessions.filter(status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED))
    payments = InvoicePayment.objects.for_photographer(profile).filter(status=InvoicePayment.Status.COMPLETED)
    refunds = PaymentRefund.objects.for_photographer(profile).filter(status=PaymentRefund.Status.COMPLETED)
    session_ids = sessions.values("pk")
    if any(selected.values()):
        payments = payments.filter(invoice__booking_id__in=session_ids)
        refunds = refunds.filter(payment__invoice__booking_id__in=session_ids)

    def values(a, b):
        if a is None: return None
        ps = period(payments, "paid_at", a, b)
        revenue = ps.aggregate(v=Sum("amount"))["v"] or Decimal("0")
        fees = ps.aggregate(v=Sum("processor_fee"))["v"] or Decimal("0")
        returned = period(refunds, "refunded_at", a, b).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        bs = period(booked, "confirmed_at", a, b)
        booking_count = bs.count()
        new_clients = period(clients, "created_at", a, b).count()
        period_leads = period(leads, "created_at", a, b)
        lead_count, won = period_leads.count(), period_leads.filter(status=Lead.Status.BOOKED).count()
        views = period(events.filter(event_type=GalleryAnalyticsEvent.EventType.VIEW), "occurred_at", a, b).count()
        distinct_clients = bs.values("client_id").distinct().count()
        # A repeat client has any earlier non-cancelled booking, without creating a reporting record.
        repeat = sum(1 for client_id in bs.values_list("client_id", flat=True).distinct()
                     if booked.filter(client_id=client_id, confirmed_at__date__lt=a).exists())
        return {"revenue": revenue - returned, "net": revenue - returned - fees, "bookings": booking_count,
                "clients": new_clients, "conversion": Decimal(won * 100) / lead_count if lead_count else Decimal("0"),
                "average": (bs.aggregate(v=Sum("booking_value"))["v"] or 0) / booking_count if booking_count else Decimal("0"),
                "views": views, "repeat": Decimal(repeat * 100) / distinct_clients if distinct_clients else Decimal("0")}
    current, previous = values(start, end), values(previous_start, previous_end)
    compare_label = dict(COMPARES)[compare_key]
    money = lambda v: _money(v, getattr(profile, "default_currency", "USD"))
    integer, percent = lambda v: f"{v:,}", lambda v: f"{v:.1f}%"
    specs = [
        ("Total revenue", "revenue", money, "bi-currency-dollar", "Completed payments less completed refunds received in this period.", "financial_overview"),
        ("Net revenue", "net", money, "bi-wallet2", "Total revenue less recorded payment processor fees; operating costs are not available.", "transactions"),
        ("Total bookings", "bookings", integer, "bi-calendar-check", "Bookings confirmed or completed during this period.", "bookings"),
        ("New clients", "clients", integer, "bi-people", "Client records created during this period.", "crm"),
        ("Lead-to-booking conversion", "conversion", percent, "bi-funnel", "Share of leads created in the period currently marked booked.", "growth"),
        ("Average booking value", "average", money, "bi-receipt", "Total recorded booking value divided by confirmed and completed bookings.", "bookings"),
        ("Gallery views", "views", integer, "bi-eye", "First-party gallery view events recorded during this period.", "galleries"),
        ("Repeat booking rate", "repeat", percent, "bi-arrow-repeat", "Share of booked clients in this period who had an earlier booking.", "crm"),
    ]
    metrics = [_metric(label, current[key], previous[key] if previous is not None else None, formatter, icon,
                       tip, f"{base_url.rsplit('/analytics/', 1)[0]}/{target}/", compare_label,
                       [previous[key] if previous else current[key], current[key]])
               for label, key, formatter, icon, tip, target in specs]

    def choices(qs, field): return [x for x in qs.order_by(field).values_list(field, flat=True).distinct() if x]
    all_sessions = ClientSession.objects.for_photographer(profile)
    all_leads = Lead.objects.for_photographer(profile)
    packages = InvoiceLineItem.objects.filter(invoice__photographer=profile, item_type=InvoiceLineItem.ItemType.PACKAGE)
    options = {"location": choices(all_sessions, "location"), "service": choices(all_sessions, "session_type"),
               "package": choices(packages, "description"), "lead_source": choices(all_leads, "lead_source"),
               "client_type": Client.ClientType.choices, "booking_status": ClientSession.Status.choices,
               "gallery_status": Gallery.Status.choices, "member": [("me", str(profile))]}
    labels = {"location": "Location", "member": "Photographer / team member", "service": "Service type",
              "package": "Package", "lead_source": "Lead source", "client_type": "Client type",
              "booking_status": "Booking status", "gallery_status": "Gallery status"}
    chips = [{"key": key, "label": labels[key], "value": value, "display": dict(options[key]).get(value, value) if options[key] and isinstance(options[key][0], (tuple, list)) else value}
             for key, value in selected.items() if value]
    has_any_data = any(m["raw"] for m in metrics)
    return {"range_options": RANGES, "range_key": range_key, "compare_options": COMPARES, "compare_key": compare_key,
            "start": start, "end": end, "selected_filters": selected, "filter_options": options,
            "active_chips": chips, "analytics_metrics": metrics, "has_any_data": has_any_data,
            "partial_message": "Net revenue excludes operating expenses because expense records are not available."}
