"""Owner-scoped selectors for the Growth Overview summary cards."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count, DecimalField, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientActivity, ClientSession, InvoicePayment, Lead
from apps.dashboard.financial import format_currency
from apps.dashboard.models import ReferralAttribution, ReferralLink, Review, ReviewRequest

ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


@dataclass(frozen=True)
class GrowthWindow:
    start: date | None
    end: date
    previous_start: date | None
    previous_end: date | None
    label: str


def growth_window(range_key, today=None):
    """Return an inclusive range and its previous, equally sized range."""
    today = today or timezone.localdate()
    if range_key == "all_time":
        return GrowthWindow(None, today, None, None, "all-time total")
    if range_key == "this_year":
        start = date(today.year, 1, 1)
    elif range_key == "this_quarter":
        start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
    else:
        days = 90 if range_key == "last_90_days" else 30
        start = today - timedelta(days=days - 1)
    duration = (today - start).days + 1
    previous_end = start - timedelta(days=1)
    return GrowthWindow(start, today, previous_end - timedelta(days=duration - 1), previous_end,
                        "vs previous equivalent period")


def _during(queryset, field, start, end):
    filters = {f"{field}__date__lte": end}
    if start:
        filters[f"{field}__date__gte"] = start
    return queryset.filter(**filters)


def _confirmed_during(queryset, start, end):
    """Filter bookings by confirmation, independently of request/session dates."""
    return _during(queryset, "confirmed_at", start, end)


def _percent(numerator, denominator):
    if not denominator:
        return None
    return (Decimal(numerator) / Decimal(denominator) * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _period_values(profile, start, end):
    leads = _during(Lead.objects.for_photographer(profile), "created_at", start, end)
    bookings = _confirmed_during(ClientSession.objects.for_photographer(profile).filter(
        status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)), start, end)
    booking_count = bookings.count()
    booking_total = bookings.aggregate(total=Coalesce(
        Sum("booking_value"), Value(ZERO), output_field=MONEY_FIELD))["total"]
    referral_count = bookings.filter(
        Q(referral_attribution__isnull=False) |
        Q(client__converted_lead__lead_source__iregex=r"referr")
    ).distinct().count()
    repeat_count = 0
    for booking in bookings.only("client_id", "confirmed_at"):
        if ClientSession.objects.for_photographer(profile).filter(
            client_id=booking.client_id, status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED),
            confirmed_at__lt=booking.confirmed_at).exists():
            repeat_count += 1
    return {"new_leads": leads.count(), "confirmed_bookings": booking_count,
            "conversion_rate": _percent(leads.filter(status=Lead.Status.BOOKED).count(), leads.count()),
            "average_booking_value": (booking_total / Decimal(booking_count)).quantize(Decimal("0.01")) if booking_count else None,
            "repeat_client_rate": _percent(repeat_count, booking_count), "referral_bookings": referral_count}


def _comparison(current, previous):
    if current is None or previous in (None, ZERO, 0):
        return None, "neutral"
    change = ((Decimal(current) - Decimal(previous)) / abs(Decimal(previous)) * HUNDRED).quantize(Decimal("0.1"))
    return change, "positive" if change > ZERO else "negative" if change < ZERO else "neutral"


def growth_summary(profile, range_key, currency="USD", today=None):
    """Build six display-ready metrics without exposing aggregation to templates."""
    window = growth_window(range_key, today)
    current = _period_values(profile, window.start, window.end)
    previous = _period_values(profile, window.previous_start, window.previous_end) if window.previous_end else None
    definitions = [
        ("New leads", "new_leads", "Leads created during the selected period.", "New inquiries received", "photographer_workspace:leads", "count", "bi-person-plus"),
        ("Confirmed bookings", "confirmed_bookings", "Bookings confirmed during the selected period.", "Confirmed and completed sessions", "photographer_workspace:bookings", "count", "bi-calendar-check"),
        ("Lead conversion rate", "conversion_rate", "Booked leads divided by all leads created in the period.", "Each lead is counted once", "photographer_workspace:leads", "rate", "bi-funnel"),
        ("Average booking value", "average_booking_value", "Total confirmed booking value divided by confirmed bookings.", "Based on confirmed booking value", "photographer_workspace:bookings", "money", "bi-cash-stack"),
        ("Repeat client rate", "repeat_client_rate", "Bookings from returning clients divided by eligible bookings.", "Clients with an earlier confirmed booking", "photographer_workspace:clients", "rate", "bi-arrow-repeat"),
        ("Referral bookings", "referral_bookings", "Confirmed bookings attributed to a referral lead source.", "Referral-attributed confirmations", "photographer_workspace:referrals", "count", "bi-people"),
    ]
    cards = []
    for title, key, tooltip, detail, url_name, kind, icon in definitions:
        value = current[key]
        percentage, trend = _comparison(value, previous[key] if previous else None)
        formatted = "—" if value is None else (format_currency(value, currency) if kind == "money" else f"{value}%" if kind == "rate" else f"{value:,}")
        cards.append({"title": title, "value": value, "formatted_value": formatted, "percentage": percentage,
                      "trend": trend, "period_label": window.label, "tooltip": tooltip,
                      "supporting_value": detail, "url": reverse(url_name), "icon": icon})
    return {"cards": cards, "values": current, "window": window}


def _format_duration(delta):
    """Return a compact, readable age for a stage without implying false precision."""
    hours = max(0, int(delta.total_seconds() // 3600))
    if hours < 24:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"
    days = hours // 24
    return f"{days} day" if days == 1 else f"{days} days"


def lead_funnel(profile, range_key, currency="USD", today=None):
    """Build the date-scoped lead and booking stage snapshot."""
    window = growth_window(range_key, today)
    leads = _during(Lead.objects.for_photographer(profile).filter(archived_at__isnull=True),
                    "created_at", window.start, window.end)
    session_base = ClientSession.objects.for_photographer(profile)
    sessions = _during(session_base.filter(status__in=(ClientSession.Status.TENTATIVE,
                       ClientSession.Status.CANCELLED)), "created_at", window.start, window.end)
    confirmed_sessions = _confirmed_during(session_base.filter(
        status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)), window.start, window.end)
    now = timezone.now()
    stage_specs = [
        ("New lead", leads.filter(status=Lead.Status.NEW), "leads", Lead.Status.NEW, "estimated_value"),
        ("Contacted", leads.filter(status=Lead.Status.CONTACTED), "leads", Lead.Status.CONTACTED, "estimated_value"),
        ("Consultation scheduled", leads.filter(status=Lead.Status.CONSULTATION), "leads", Lead.Status.CONSULTATION, "estimated_value"),
        ("Proposal or quote sent", leads.filter(status=Lead.Status.PROPOSAL_SENT), "leads", Lead.Status.PROPOSAL_SENT, "estimated_value"),
        ("Booking pending", sessions.filter(status=ClientSession.Status.TENTATIVE), "bookings", ClientSession.Status.TENTATIVE, "booking_value"),
        ("Confirmed booking", confirmed_sessions, "bookings", ClientSession.Status.CONFIRMED, "booking_value"),
    ]
    stages, first_count, previous_count = [], None, None
    for label, queryset, destination, status, value_field in stage_specs:
        records = list(queryset)
        count = len(records)
        first_count = count if first_count is None else first_count
        total = sum((getattr(record, value_field) or ZERO for record in records), ZERO)
        ages = [(record.updated_at if isinstance(record, Lead) else now) - record.created_at for record in records]
        average_age = sum(ages, timedelta()) / len(ages) if ages else None
        url_name = "photographer_workspace:leads" if destination == "leads" else "photographer_workspace:bookings"
        stages.append({
            "label": label, "count": count, "previous_rate": _percent(count, previous_count),
            "overall_rate": _percent(count, first_count), "formatted_value": format_currency(total, currency),
            "average_time": _format_duration(average_age) if average_age else None,
            "url": f"{reverse(url_name)}?status={status}",
        })
        previous_count = count
    return stages


SOURCE_LABELS = {
    "website": "Website", "google": "Google", "instagram": "Instagram", "facebook": "Facebook",
    "tiktok": "TikTok", "tik tok": "TikTok", "pinterest": "Pinterest", "referral": "Referral",
    "client referral": "Referral", "returning client": "Returning client", "partner": "Partner",
    "paid advertising": "Paid advertising", "paid ads": "Paid advertising", "direct inquiry": "Direct inquiry",
    "direct": "Direct inquiry", "other": "Other",
}


def _source_label(value):
    normalized = " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())
    return SOURCE_LABELS.get(normalized, "Unknown" if not normalized else "Other")


def lead_source_performance(profile, range_key, currency="USD", sort_key="leads", today=None):
    """Aggregate leads and their real converted bookings under stable source labels."""
    window = growth_window(range_key, today)
    leads = list(_during(Lead.objects.for_photographer(profile).filter(archived_at__isnull=True),
                         "created_at", window.start, window.end))
    rows = {}
    qualified = {Lead.Status.CONTACTED, Lead.Status.CONSULTATION, Lead.Status.PROPOSAL_SENT, Lead.Status.BOOKED}
    for lead in leads:
        label = _source_label(lead.lead_source)
        row = rows.setdefault(label, {"source": label, "source_value": lead.lead_source or "__unknown__",
                                      "leads": 0, "qualified_leads": 0,
                                      "bookings": 0, "booking_value": ZERO})
        row["leads"] += 1
        row["qualified_leads"] += lead.status in qualified
    bookings = _confirmed_during(ClientSession.objects.for_photographer(profile).filter(
        status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED),
        client__converted_lead__isnull=False), window.start, window.end).select_related("client__converted_lead")
    converted_sources = set()
    for booking in bookings:
        label = _source_label(booking.client.converted_lead.lead_source)
        row = rows.setdefault(label, {"source": label, "source_value": booking.client.converted_lead.lead_source or "__unknown__",
                                      "leads": 0, "qualified_leads": 0,
                                      "bookings": 0, "booking_value": ZERO})
        row["booking_records"] = row.get("booking_records", 0) + 1
        attribution = (label, booking.client.converted_lead_id)
        if attribution not in converted_sources:
            row["bookings"] += 1
            converted_sources.add(attribution)
        row["booking_value"] += booking.booking_value or ZERO
    for row in rows.values():
        row["conversion_rate"] = _percent(row["bookings"], row["leads"])
        row["average_value"] = row["booking_value"] / row.get("booking_records", 0) if row.get("booking_records") else None
        row["formatted_booking_value"] = format_currency(row["booking_value"], currency)
        row["formatted_average_value"] = format_currency(row["average_value"], currency) if row["average_value"] is not None else "—"
        row["url"] = f'{reverse("photographer_workspace:leads")}?source={row["source_value"]}'
    sort_fields = {"leads": "leads", "bookings": "bookings", "conversion": "conversion_rate", "value": "booking_value"}
    field = sort_fields.get(sort_key, "leads")
    return sorted(rows.values(), key=lambda row: (row[field] is not None, row[field] or ZERO, row["source"]), reverse=True)


def booking_value_by_source(profile, range_key, metric="booking_value", show_all=False, currency="USD", today=None):
    """Return chart-ready acquisition results with payments attributed in bulk."""
    window = growth_window(range_key, today)
    rows = {label: {"source": label, "booking_value": ZERO, "collected_revenue": ZERO, "bookings": 0}
            for label in set(SOURCE_LABELS.values()) | {"Unknown"}} if show_all else {}
    bookings = (_confirmed_during(ClientSession.objects.for_photographer(profile).filter(
        status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED),
        client__converted_lead__isnull=False), window.start, window.end)
        .values("client__converted_lead__lead_source").annotate(
            bookings=Count("id"), booking_value=Coalesce(Sum("booking_value"), Value(ZERO), output_field=MONEY_FIELD)))
    for result in bookings:
        label = _source_label(result["client__converted_lead__lead_source"])
        row = rows.setdefault(label, {"source": label, "booking_value": ZERO, "collected_revenue": ZERO, "bookings": 0})
        row["bookings"] += result["bookings"]
        row["booking_value"] += result["booking_value"]
    payments = (_during(InvoicePayment.objects.for_photographer(profile).filter(
        status=InvoicePayment.Status.COMPLETED, invoice__booking__isnull=False,
        invoice__booking__client__converted_lead__isnull=False), "paid_at", window.start, window.end)
        .values("invoice__booking__client__converted_lead__lead_source").annotate(
            total=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY_FIELD)))
    for result in payments:
        label = _source_label(result["invoice__booking__client__converted_lead__lead_source"])
        row = rows.setdefault(label, {"source": label, "booking_value": ZERO, "collected_revenue": ZERO, "bookings": 0})
        row["collected_revenue"] += result["total"]
    metric = metric if metric in {"booking_value", "collected_revenue", "bookings"} else "booking_value"
    total = sum((row[metric] for row in rows.values()), ZERO)
    maximum = max((row[metric] for row in rows.values()), default=ZERO)
    output = []
    for row in sorted(rows.values(), key=lambda item: (item[metric], item["source"]), reverse=True):
        if not show_all and not (row["bookings"] or row["booking_value"] or row["collected_revenue"]):
            continue
        value = row[metric]
        output.append({**row, "value": value, "percent": _percent(value, total) or ZERO,
                       "bar_percent": round(float(Decimal(value) / Decimal(maximum) * HUNDRED), 2) if maximum else 0,
                       "formatted_value": f"{value:,}" if metric == "bookings" else format_currency(value, currency)})
    return {"rows": output, "metric": metric, "total": total,
            "summary": "; ".join(f'{row["source"]}: {row["formatted_value"]}, {row["bookings"]} bookings, {row["percent"]}% of total' for row in output)}


def service_performance(profile, range_key, currency="USD", today=None):
    """Aggregate configured/custom service labels without per-row database work."""
    window = growth_window(range_key, today)
    previous_start, previous_end = window.previous_start, window.previous_end
    leads = (_during(Lead.objects.for_photographer(profile).filter(archived_at__isnull=True),
                     "created_at", window.start, window.end).values("event_type").annotate(
        leads=Count("id"), converted=Count("id", filter=Q(status=Lead.Status.BOOKED))))
    sessions = (_confirmed_during(ClientSession.objects.for_photographer(profile).filter(
                status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)), window.start, window.end)
                .values("session_type").annotate(
                    bookings=Count("id", distinct=True), cancelled=Value(0, output_field=IntegerField()),
                    booking_value=Coalesce(Sum("booking_value"), Value(ZERO), output_field=MONEY_FIELD)))
    cancellations = (_during(ClientSession.objects.for_photographer(profile).filter(
                     status=ClientSession.Status.CANCELLED), "created_at", window.start, window.end)
                     .values("session_type").annotate(cancelled=Count("id", distinct=True)))
    previous = {}
    if previous_end:
        previous = {item["session_type"]: item["value"] for item in
                    _confirmed_during(ClientSession.objects.for_photographer(profile).filter(status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)),
                                      previous_start, previous_end).values("session_type").annotate(value=Sum("booking_value"))}
    rows = {}
    for item in leads:
        name = (item["event_type"] or "Unspecified service").strip()
        rows[name] = {"service": name, "leads": item["leads"], "converted": item["converted"], "bookings": 0, "cancelled": 0, "booking_value": ZERO}
    for item in sessions:
        name = (item["session_type"] or "Unspecified service").strip()
        row = rows.setdefault(name, {"service": name, "leads": 0, "converted": 0, "bookings": 0, "cancelled": 0, "booking_value": ZERO})
        row.update({key: item[key] for key in ("bookings", "cancelled", "booking_value")})
    for item in cancellations:
        name = (item["session_type"] or "Unspecified service").strip()
        row = rows.setdefault(name, {"service": name, "leads": 0, "converted": 0, "bookings": 0,
                                     "cancelled": 0, "booking_value": ZERO})
        row["cancelled"] = item["cancelled"]
    output = []
    for row in rows.values():
        total_sessions = row["bookings"] + row["cancelled"]
        prior = previous.get(row["service"], ZERO)
        growth, _ = _comparison(row["booking_value"], prior)
        output.append({**row, "conversion_rate": _percent(row["converted"], row["leads"]),
                       "average_value": row["booking_value"] / row["bookings"] if row["bookings"] else None,
                       "growth": growth, "cancellation_rate": _percent(row["cancelled"], total_sessions),
                       "formatted_value": format_currency(row["booking_value"], currency),
                       "formatted_average": format_currency(row["booking_value"] / row["bookings"], currency) if row["bookings"] else "—",
                       "url": f'{reverse("photographer_workspace:bookings")}?service={row["service"]}'})
    if output:
        fastest = max(output, key=lambda row: row["growth"] if row["growth"] is not None else Decimal("-Infinity"))
        highest = max(output, key=lambda row: row["booking_value"])
        converting = max(output, key=lambda row: row["conversion_rate"] if row["conversion_rate"] is not None else Decimal("-1"))
        losing = min(output, key=lambda row: row["growth"] if row["growth"] is not None else Decimal("Infinity"))
        for row in output:
            row["badges"] = (["Fastest growing"] if row is fastest and row["growth"] is not None else []) + (["Highest value"] if row is highest else []) + (["Best converting"] if row is converting and row["conversion_rate"] is not None else []) + (["Losing momentum"] if row is losing and row["growth"] is not None and row["growth"] < 0 else [])
    return sorted(output, key=lambda row: (row["booking_value"], row["service"]), reverse=True)


def reputation_summary(profile, range_key, today=None):
    """Summarize native and manually tracked external reviews; no external sync is implied."""
    window = growth_window(range_key, today)
    all_reviews = Review.objects.for_photographer(profile)
    reviews = _during(all_reviews, "reviewed_at", window.start, window.end)
    requests = _during(ReviewRequest.objects.for_photographer(profile), "sent_at", window.start, window.end)
    total_requests = requests.count()
    distribution = {row["rating"]: row["count"] for row in reviews.values("rating").annotate(count=Count("id"))}
    sources = list(reviews.values("source", "source_name").annotate(count=Count("id"), average=Avg("rating")).order_by("-count"))
    for source in sources:
        source["label"] = source["source_name"] or ("LumisPixel" if source["source"] == Review.Source.LUMISPIXEL else "External")
        source["average"] = Decimal(source["average"]).quantize(Decimal("0.1"))
    average = reviews.aggregate(value=Avg("rating"))["value"]
    return {"metrics": [("Average rating", f'{Decimal(average).quantize(Decimal("0.1"))} / 5' if average else "—"),
                        ("Total reviews", reviews.count()), ("New reviews", reviews.count()),
                        ("Pending review requests", requests.filter(completed_at__isnull=True).count()),
                        ("Review-request conversion rate", f'{_percent(requests.filter(completed_at__isnull=False).count(), total_requests)}%' if total_requests else "—"),
                        ("Reviews requiring a response", reviews.filter(source=Review.Source.LUMISPIXEL, response="").count())],
            "distribution": [(stars, distribution.get(stars, 0)) for stars in range(5, 0, -1)],
            "sources": sources, "recent": reviews.first(), "has_data": reviews.exists() or total_requests}


def referral_summary(profile, range_key, currency="USD", today=None):
    """Summarize referral records while retaining the lead and booking as sources of truth."""
    window = growth_window(range_key, today)
    links = _during(ReferralLink.objects.for_photographer(profile), "created_at", window.start, window.end)
    owned_attrs = ReferralAttribution.objects.for_photographer(profile).select_related("lead", "booking", "referral_link")
    attrs = _during(owned_attrs, "lead__created_at", window.start, window.end)
    bookings = _during(owned_attrs.filter(
        booking__status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)),
        "booking__confirmed_at", window.start, window.end)
    value = bookings.aggregate(total=Coalesce(Sum("booking__booking_value"), Value(ZERO), output_field=MONEY_FIELD))["total"]
    top = attrs.values("referral_link__referrer_name", "referral_link__referral_type").annotate(
        leads=Count("id"), bookings=Count("booking", filter=Q(booking__status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)))).order_by("-bookings", "-leads")[:5]
    visits = links.aggregate(total=Sum("visits"))["total"]
    return {"metrics": [("Referral links created", links.count()), ("Referral visits", visits if visits is not None else "—"),
                        ("Leads generated", attrs.count()), ("Confirmed bookings", bookings.count()),
                        ("Referral conversion rate", f'{_percent(bookings.count(), attrs.count())}%' if attrs.exists() else "—"),
                        ("Referral booking value", format_currency(value, currency))],
            "links": links.order_by("-created_at")[:4], "top": top, "has_data": links.exists() or attrs.exists()}


def retention_summary(profile, range_key, currency="USD", today=None):
    """Derive retention from existing clients and bookings using transparent history rules."""
    today = today or timezone.localdate()
    window = growth_window(range_key, today)
    clients = _during(Client.objects.for_photographer(profile), "created_at", window.start, window.end)
    eligible = list(_confirmed_during(ClientSession.objects.for_photographer(profile).filter(status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)), window.start, window.end).select_related("client"))
    histories = {}
    for booking in ClientSession.objects.for_photographer(profile).filter(status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)).select_related("client").order_by("starts_at"):
        histories.setdefault(booking.client_id, []).append(booking)
    returning_ids = {booking.client_id for booking in eligible if any(old.starts_at < booking.starts_at for old in histories[booking.client_id])}
    gaps = [(later.starts_at - earlier.starts_at).days for history in histories.values() for earlier, later in zip(history, history[1:])]
    total = sum((booking.booking_value or ZERO for booking in eligible), ZERO)
    due = [{"client": history[-1].client, "last_session": history[-1].starts_at.date(), "session_type": history[-1].session_type}
           for history in histories.values() if history[-1].starts_at.date() <= today - timedelta(days=365)]
    return {"metrics": [("New clients", clients.count()), ("Returning clients", len(returning_ids)),
                        ("Repeat booking rate", f'{_percent(len(returning_ids), len(eligible))}%' if eligible else "—"),
                        ("Avg. time between bookings", f"{round(sum(gaps) / len(gaps))} days" if gaps else "—"),
                        ("Avg. client booking value", format_currency(total / len(eligible), currency) if eligible else "—"),
                        ("Clients potentially due", len(due))], "due": due[:5], "has_data": bool(histories),
            "rule": "Clients whose latest confirmed or completed session was at least 12 months ago."}


def growth_opportunities(profile, show_all=False, today=None):
    """Turn current, owner-scoped records into transparent next actions."""
    today = today or timezone.localdate()
    now = timezone.now()
    leads = Lead.objects.for_photographer(profile).filter(archived_at__isnull=True)
    bookings = ClientSession.objects.for_photographer(profile)
    items = []

    def add(title, explanation, priority, count, metric, action, url, icon):
        if count:
            items.append({"title": title, "explanation": explanation, "priority": priority,
                          "count": count, "metric": metric, "action": action, "url": url, "icon": icon})

    overdue = leads.filter(status__in=(Lead.Status.NEW, Lead.Status.CONTACTED, Lead.Status.PROPOSAL_SENT)).filter(
        Q(next_follow_up__lt=today) | Q(next_follow_up__isnull=True, created_at__lt=now - timedelta(days=3)))
    add("Leads need a follow-up", "Open leads have an overdue follow-up or have waited at least three days without one.",
        "High", overdue.count(), "Overdue or unscheduled follow-up", "Review and contact leads",
        f'{reverse("photographer_workspace:leads")}?follow_up=overdue', "bi-person-check")
    consultations = leads.filter(status=Lead.Status.CONSULTATION, updated_at__lt=now - timedelta(days=2))
    add("Consultations need a decision", "Consultation-stage leads have had no recorded decision for at least two days.",
        "High", consultations.count(), "2+ days in consultation", "Record the next decision",
        f'{reverse("photographer_workspace:leads")}?status={Lead.Status.CONSULTATION}', "bi-chat-square-text")
    completed_without_request = bookings.filter(status=ClientSession.Status.COMPLETED).exclude(
        client__review_requests__isnull=False).values("client_id").distinct()
    add("Ask completed clients for a review", "Clients with a completed session have no review request on record.",
        "Medium", completed_without_request.count(), "No review request recorded", "Send review requests",
        reverse("photographer_workspace:reviews"), "bi-star")
    missing_source = bookings.filter(status=ClientSession.Status.CONFIRMED).filter(
        Q(client__converted_lead__isnull=True) | Q(client__converted_lead__lead_source=""))
    add("Add missing lead sources", "Confirmed bookings cannot be attributed because their lead source is blank.",
        "Medium", missing_source.count(), "Confirmed bookings without source", "Record lead sources",
        f'{reverse("photographer_workspace:bookings")}?source=missing', "bi-signpost-split")
    referral_leads = leads.filter(referral_attribution__isnull=False).exclude(
        status__in=(Lead.Status.BOOKED, Lead.Status.LOST)).filter(last_contacted_at__isnull=True)
    add("Follow up with referral leads", "Referral-attributed leads have no contact recorded yet.",
        "High", referral_leads.count(), "No contact recorded", "Contact referral leads",
        reverse("photographer_workspace:referrals"), "bi-people")
    due_ids = []
    for client in Client.objects.for_photographer(profile):
        latest = bookings.filter(client=client, status__in=(ClientSession.Status.CONFIRMED,
                                 ClientSession.Status.COMPLETED)).order_by("-starts_at").first()
        if latest and latest.starts_at.date() <= today - timedelta(days=365):
            due_ids.append(client.pk)
    add("Reconnect with past clients", "These clients’ latest confirmed or completed session was at least one year ago.",
        "Informational", len(due_ids), "12+ months since latest session", "Review clients to reconnect with",
        reverse("photographer_workspace:clients"), "bi-arrow-repeat")
    rank = {"High": 0, "Medium": 1, "Informational": 2}
    items.sort(key=lambda item: (rank[item["priority"]], -item["count"], item["title"]))
    return {"items": items if show_all else items[:4], "total": len(items), "has_more": not show_all and len(items) > 4}


def recent_growth_activity(profile, limit=12):
    """Return CRM growth events already recorded by the workspace."""
    supported = {
        ClientActivity.EventType.LEAD_CREATED: "New lead received",
        ClientActivity.EventType.EMAIL_SENT: "Lead contacted",
        ClientActivity.EventType.CONSULTATION_SCHEDULED: "Consultation scheduled",
        ClientActivity.EventType.LEAD_CONVERTED: "Lead converted",
        ClientActivity.EventType.LEAD_BOOKED: "Lead converted",
        ClientActivity.EventType.LEAD_LOST: "Lead marked lost",
    }
    records = (ClientActivity.objects.for_photographer(profile).filter(event_type__in=supported)
               .select_related("lead", "client").order_by("-occurred_at")[:limit])
    rows = []
    for record in records:
        person = record.lead or record.client
        metadata = record.metadata if isinstance(record.metadata, dict) else {}
        rows.append({"activity": supported[record.event_type], "person": str(person) if person else "—",
                     "source": record.lead.lead_source if record.lead and record.lead.lead_source else "—",
                     "related": metadata.get("booking") or metadata.get("campaign") or "—",
                     "team_member": metadata.get("team_member") or "—", "occurred_at": record.occurred_at,
                     "url": (f'{reverse("photographer_workspace:leads")}?lead={record.lead_id}' if record.lead_id
                             else reverse("photographer_workspace:clients"))})
    return rows
