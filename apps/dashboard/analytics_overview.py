"""Read-only, cross-product analytics assembled from LumisPixel source records."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.clients.models import (Client, ClientActivity, ClientInvoice, ClientSession, ClientTask,
                                 InvoiceLineItem, InvoicePayment, Lead, PaymentRefund)
from apps.galleries.models import Gallery, GalleryAnalyticsEvent, GalleryInvitation, GalleryOrder


RANGES = (("30_days", "Last 30 days"), ("this_month", "This month"),
          ("this_quarter", "This quarter"), ("this_year", "This year"), ("custom", "Custom range"))
COMPARES = (("previous_period", "Previous period"), ("previous_year", "Previous year"), ("none", "No comparison"))
GROUPINGS = (("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"))


def _short_date(value):
    """Format a compact date without POSIX-only ``strftime`` directives."""
    return f"{value:%b} {value.day}"


def _analytics_insights(current, previous, payment_ratio, invoiced, collected,
                        cancellation_rate, customer, gallery, operations, urls, currency):
    """Return at most six deterministic recommendations, ordered by business impact.

    Rule catalogue (thresholds are intentionally fixed and are not predictions):
    growth opportunity: a lead source has >=3 leads and converts >=15 points above
    the next source; revenue opportunity: revenue is >=10% above a non-zero prior
    period; conversion issue: >=5 leads convert below 20% or conversion falls 10
    points; client retention: >=3 bookings repeat below 20% or fall 10 points;
    booking risk: cancellation is >=15%; gallery engagement: >=10 views engage
    below 10%; operational bottleneck: >=3 overdue tasks; payment risk: collection
    is below 85%; team capacity: utilization is above 85% or below 25% with work;
    data quality issue: activity exists while editing/team assignment data is absent.

    Scores combine fixed urgency and impact bands. Higher scores sort first, with
    the stable rule id breaking ties. No random, predictive, or AI-generated text
    is used.
    """
    insights = []

    def add(rule_id, category, severity, urgency, impact, title, explanation,
            metric, action, url, tone="risk", icon="bi-exclamation-circle", dismissible=True):
        insights.append({"id": rule_id, "category": category, "severity": severity,
                         "score": urgency * 10 + impact, "title": title,
                         "explanation": explanation, "metric": metric, "action": action,
                         "url": url, "tone": tone, "icon": icon, "dismissible": dismissible})

    money = lambda value: _money(value, currency)
    bookings = current["bookings"]
    leads = sum(source["value"] for source in customer["sources"])
    sources = sorted((source for source in customer["sources"] if source["value"] >= 3),
                     key=lambda source: (-source["conversion"], source["label"]))
    if len(sources) >= 2 and sources[0]["conversion"] - sources[1]["conversion"] >= 15:
        best, difference = sources[0], sources[0]["conversion"] - sources[1]["conversion"]
        add("growth-source", "Growth opportunity", "Opportunity", 3, min(9, best["value"]),
            f'{best["label"]} leads convert better',
            f'{best["label"]} has the strongest observed conversion rate among sources with at least three leads.',
            f'{best["conversion"]:.1f}% conversion · {difference:.1f} points ahead',
            f'Review {best["label"]} leads', best["url"], "opportunity", "bi-graph-up-arrow")
    if previous and previous["revenue"] > 0:
        change = (current["revenue"] - previous["revenue"]) * 100 / previous["revenue"]
        if change >= 10:
            add("revenue-growth", "Revenue opportunity", "High opportunity", 3, min(9, int(change / 5)),
                "Revenue increased", "Collected revenue less refunds improved against the comparison period.",
                f'{money(current["revenue"])} · +{change:.1f}%', "Review revenue drivers", urls["financial"],
                "opportunity", "bi-currency-dollar")
    conversion_drop = previous and previous["conversion"] - current["conversion"] >= 10
    if leads >= 5 and (current["conversion"] < 20 or conversion_drop):
        add("conversion-low", "Conversion issue", "Needs attention", 4, min(9, leads),
            "Lead conversion needs attention", "A smaller-than-expected share of recorded leads is marked booked.",
            f'{current["conversion"]:.1f}% · {leads} leads', "Review the lead funnel", urls["growth"])
    repeat_drop = previous and previous["repeat"] - current["repeat"] >= 10
    if bookings >= 3 and (current["repeat"] < 20 or repeat_drop):
        add("retention-low", "Client retention", "Needs attention", 3, min(9, bookings),
            "Repeat bookings are low", "Few clients booked this period after having booked previously.",
            f'{current["repeat"]:.1f}% repeat booking rate', "Review returning clients", urls["clients"],
            "risk", "bi-arrow-repeat")
    if cancellation_rate is not None and cancellation_rate >= 15:
        add("booking-cancellations", "Booking risk", "Urgent" if cancellation_rate >= 25 else "Watch closely",
            5 if cancellation_rate >= 25 else 4, min(9, int(cancellation_rate / 5)), "Cancellations are elevated",
            "The share of scheduled sessions marked cancelled is above the fixed 15% threshold.",
            f'{cancellation_rate:.1f}% cancellation rate', "Review cancelled bookings", urls["bookings"])
    raw_gallery = gallery["raw"]
    if raw_gallery["views"] >= 10 and raw_gallery["engagement"] < 10:
        add("gallery-engagement", "Gallery engagement", "Opportunity", 2, min(9, raw_gallery["views"] // 10),
            "Gallery engagement is low", "Views are not translating into favorites, downloads, or shares.",
            f'{raw_gallery["engagement"]:.1f}% engagement · {raw_gallery["views"]} views',
            "Review gallery performance", urls["galleries"], "opportunity", "bi-images")
    raw_ops = operations["raw"]
    if raw_ops["overdue_tasks"] >= 3:
        add("workflow-overdue", "Operational bottleneck", "Urgent" if raw_ops["overdue_tasks"] >= 8 else "Needs attention",
            5 if raw_ops["overdue_tasks"] >= 8 else 4, min(9, raw_ops["overdue_tasks"]), "Overdue work is building up",
            "Open workflow tasks have passed their due dates.", f'{raw_ops["overdue_tasks"]} overdue workflows',
            "Review overdue work", urls["clients"], "risk", "bi-exclamation-diamond")
    if raw_ops["late_deliveries"]:
        add("gallery-delivery", "Operational bottleneck", "Urgent" if raw_ops["late_deliveries"] >= 3 else "Watch closely",
            5 if raw_ops["late_deliveries"] >= 3 else 4, min(9, raw_ops["late_deliveries"] * 2),
            "Gallery deliveries are late", "Past-event galleries remain unpublished, which can affect client experience.",
            f'{raw_ops["late_deliveries"]} late gallery deliveries', "Review gallery delivery", urls["galleries"])
    if payment_ratio is not None and payment_ratio < 85:
        outstanding = max(Decimal("0"), invoiced - collected)
        add("payment-collection", "Payment risk", "Urgent" if payment_ratio < 60 else "Needs attention",
            5 if payment_ratio < 60 else 4, 9 if outstanding >= 1000 else 6,
            "Outstanding balances need attention", "The collected share of issued invoice value is below the fixed 85% threshold.",
            f'{money(outstanding)} outstanding · {payment_ratio:.1f}% collected',
            "Review outstanding invoices", urls["financial"], "risk", "bi-credit-card")
    if bookings and (raw_ops["utilization"] > 85 or raw_ops["utilization"] < 25):
        high = raw_ops["utilization"] > 85
        add("team-capacity", "Team capacity", "Needs attention" if high else "Opportunity", 3, 7,
            "Schedule capacity is tight" if high else "Schedule capacity is underused",
            "Recorded session minutes are compared with the documented eight-hour daily capacity baseline.",
            f'{raw_ops["utilization"]:.1f}% schedule utilization', "Review the schedule", urls["bookings"],
            "risk" if high else "opportunity", "bi-people")
    if any(current.values()):
        add("missing-operational-data", "Data quality issue", "Data needed", 1, 1,
            "Some workflow insights are unavailable", "Editing completion and team assignments do not have dedicated records, so no estimates are shown.",
            "2 operational fields not tracked", "Review operational data", urls["clients"], "info", "bi-database-check")
    return sorted(insights, key=lambda item: (-item["score"], item["id"]))[:6]


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
    return {"label": label, "raw": value, "value": display(value), "previous_value": display(previous) if previous is not None else "Unavailable", "change": change, "tone": tone,
            "direction": direction, "icon": icon, "note": note, "tooltip": tooltip, "url": url, "spark": heights}


def _business_health(current, previous, payment_ratio, cancellation_rate, urls):
    """Build a normalized, rule-based score from only the signals we can observe."""
    def trend(now, before):
        if before is None or before == 0:
            return None
        change = (Decimal(str(now)) - Decimal(str(before))) / Decimal(str(before)) * 100
        return (100 if change >= 10 else 80 if change >= 0 else 45 if change >= -10 else 10), change

    rules = []
    for label, key, weight, url in (
        ("Revenue trend", "revenue", 20, urls["financial"]),
        ("Booking trend", "bookings", 15, urls["bookings"]),
        ("Lead conversion trend", "conversion", 15, urls["growth"]),
        ("Gallery engagement", "views", 10, urls["galleries"]),
    ):
        result = trend(current[key], previous[key] if previous else None)
        if result:
            rating, change = result
            rules.append((label, weight, rating, f"{change:+.1f}% vs comparison period", url))
    if current["bookings"]:
        rating = 100 if current["repeat"] >= 40 else 75 if current["repeat"] >= 25 else 45 if current["repeat"] >= 10 else 20
        rules.append(("Repeat client rate", 10, rating, f'{current["repeat"]:.1f}% of booked clients returned', urls["clients"]))
    if payment_ratio is not None:
        rating = 100 if payment_ratio >= 90 else 75 if payment_ratio >= 75 else 40 if payment_ratio >= 50 else 10
        rules.append(("Payment collection health", 15, rating, f"{payment_ratio:.1f}% of invoiced value collected", urls["financial"]))
    if cancellation_rate is not None:
        rating = 100 if cancellation_rate <= 5 else 75 if cancellation_rate <= 10 else 40 if cancellation_rate <= 20 else 10
        rules.append(("Cancellation rate", 10, rating, f"{cancellation_rate:.1f}% of scheduled sessions cancelled", urls["bookings"]))

    available_weight = sum(item[1] for item in rules)
    score = round(sum(weight * rating for _, weight, rating, _, _ in rules) / available_weight) if available_weight else None
    label = "No score" if score is None else "Excellent" if score >= 85 else "Healthy" if score >= 70 else "Needs Attention" if score >= 50 else "At Risk"
    contributions = [{"label": name, "points": round(weight * rating / 100, 1), "weight": weight,
                      "rating": rating, "detail": detail, "url": url} for name, weight, rating, detail, url in rules]
    missing = [name for name in ("Revenue trend", "Booking trend", "Lead conversion trend", "Repeat client rate",
               "Gallery engagement", "Payment collection health", "Delivery turnaround", "Cancellation rate")
               if name not in {item["label"] for item in contributions}]
    return {"score": score, "label": label, "contributions": contributions, "available_weight": available_weight,
            "missing": missing, "tooltip": "Each available signal receives a fixed weight and a rule-based rating from 0–100. Points are divided by the weights available, so missing data never lowers the score. No machine learning is used."}


def _business_trends(profile, start, end, comparison, grouping, sessions, clients, leads, events, payments, refunds, currency, urls):
    """Build all chart series with grouped aggregate queries (never one query per point)."""
    trunc = {"daily": TruncDay, "weekly": TruncWeek, "monthly": TruncMonth}[grouping]
    step = timedelta(days=1 if grouping == "daily" else 7)

    def key(value):
        value = value.date() if hasattr(value, "date") else value
        if grouping == "monthly": return value.replace(day=1)
        if grouping == "weekly": return value - timedelta(days=value.weekday())
        return value

    def buckets(a, b):
        cursor, result = key(a), []
        while cursor <= b:
            result.append(cursor)
            if grouping == "monthly":
                cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            else: cursor += step
        return result

    all_start = min(start, comparison[0]) if comparison[0] else start
    all_end = max(end, comparison[1]) if comparison[1] else end
    def grouped(qs, field, **aggregates):
        rows = qs.filter(**{f"{field}__date__gte": all_start, f"{field}__date__lte": all_end}).annotate(bucket=trunc(field)).values("bucket").annotate(**aggregates).order_by("bucket")
        return {key(row["bucket"]): row for row in rows}

    revenue = grouped(payments, "paid_at", value=Sum("amount"))
    returned = grouped(refunds, "refunded_at", value=Sum("amount"))
    booking = grouped(sessions, "confirmed_at", value=Count("pk"), total=Sum("booking_value"))
    client = grouped(clients, "created_at", value=Count("pk"))
    lead = grouped(leads, "created_at", value=Count("pk"), won=Count("pk", filter=Q(status=Lead.Status.BOOKED)))
    engagement = grouped(events, "occurred_at", value=Count("pk"))

    def raw(bucket):
        bookings = booking.get(bucket, {})
        count, total = bookings.get("value", 0), bookings.get("total") or Decimal("0")
        leads_row = lead.get(bucket, {})
        lead_count, won = leads_row.get("value", 0), leads_row.get("won", 0)
        return {"revenue": float((revenue.get(bucket, {}).get("value") or 0) - (returned.get(bucket, {}).get("value") or 0)),
                "bookings": count, "clients": client.get(bucket, {}).get("value", 0), "leads": lead_count,
                "conversion": round(won * 100 / lead_count, 1) if lead_count else 0,
                "average": float(total / count) if count else 0, "engagement": engagement.get(bucket, {}).get("value", 0)}
    current_buckets = buckets(start, end)
    comparison_buckets = buckets(*comparison) if comparison[0] else []
    labels = [_short_date(b) if grouping != "monthly" else b.strftime("%b %Y") for b in current_buckets]
    current = [raw(b) for b in current_buckets]
    compared = [raw(b) for b in comparison_buckets]
    # Align comparisons by ordinal bucket, padding partial calendar ranges safely.
    compared += [{} for _ in range(max(0, len(current) - len(compared)))]
    comparison_available = bool(comparison_buckets) and any(any(v for v in point.values()) for point in compared)

    metric_specs = (
        ("revenue", "Revenue", "money"), ("bookings", "Bookings", "number"),
        ("clients", "New clients", "number"), ("leads", "Leads", "number"),
        ("conversion", "Conversion rate", "percent"), ("average", "Average booking value", "money"),
        ("engagement", "Gallery engagement", "number"),
    )
    metric_options = [{"key": k, "label": label, "format": fmt} for k, label, fmt in metric_specs]
    service_rows = sessions.filter(confirmed_at__date__gte=start, confirmed_at__date__lte=end).values("session_type").annotate(bookings=Count("pk"), value=Sum("booking_value")).order_by("-value")[:5]
    services = [{"label": row["session_type"] or "Unspecified", "value": float(row["value"] or 0), "bookings": row["bookings"]} for row in service_rows]
    rolling = []
    for index in range(len(current)):
        beginning = max(0, index - (29 if grouping == "daily" else 3 if grouping == "weekly" else 0))
        rolling.append(sum(point["revenue"] for point in current[beginning:index + 1]))
    charts = [
        {"title": "Revenue and bookings trend", "description": "Collected revenue and confirmed bookings over time.", "metrics": ["revenue", "bookings"], "url": urls["financial"]},
        {"title": "Client growth", "description": "New client records added during each interval.", "metrics": ["clients"], "url": urls["clients"]},
        {"title": "Lead-to-booking conversion trend", "description": "The share of new leads currently marked as booked.", "metrics": ["conversion", "leads"], "url": urls["growth"]},
        {"title": "Average booking value", "description": "Recorded booking value divided by confirmed bookings.", "metrics": ["average"], "url": urls["bookings"]},
    ]
    return {"grouping_options": GROUPINGS, "grouping": grouping, "labels": labels, "current": current,
            "comparison": compared[:len(current)], "comparison_available": comparison_available,
            "metric_options": metric_options, "charts": charts, "services": services, "rolling": rolling,
            "currency": currency, "has_data": any(any(v for v in point.values()) for point in current)}


def _customer_intelligence(start, end, comparison, booked, clients, leads, payments, refunds, currency, urls):
    """Build privacy-safe customer aggregates from existing operational records."""
    def in_period(qs, field, a=start, b=end):
        return qs.filter(**{f"{field}__date__gte": a, f"{field}__date__lte": b})

    period_bookings = in_period(booked, "confirmed_at")
    booked_client_ids = set(period_bookings.values_list("client_id", flat=True))
    returning_ids = set(booked.filter(confirmed_at__date__lt=start, client_id__in=booked_client_ids)
                        .values_list("client_id", flat=True))
    new_booked_ids = booked_client_ids - returning_ids
    period_clients = in_period(clients, "created_at")
    period_leads = in_period(leads, "created_at")
    won_leads = period_leads.filter(status=Lead.Status.BOOKED).count()
    referral_clients = period_clients.filter(converted_lead__lead_source__icontains="referr").count()

    period_payments = in_period(payments, "paid_at")
    period_refunds = in_period(refunds, "refunded_at")
    collected = period_payments.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    returned = period_refunds.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    net_spend = collected - returned
    paying_clients = period_payments.values("invoice__client_id").distinct().count()
    booking_value = period_bookings.aggregate(v=Sum("booking_value"))["v"] or Decimal("0")
    response_seconds = [
        max(0, (last_contacted - created).total_seconds())
        for created, last_contacted in period_leads.exclude(last_contacted_at=None)
        .values_list("created_at", "last_contacted_at")
    ]
    average_response_hours = Decimal(str(sum(response_seconds) / len(response_seconds) / 3600)) if response_seconds else None

    def pct(a, b): return Decimal(a * 100) / b if b else Decimal("0")
    money = lambda value: _money(value, currency)
    metric_values = {
        "new": period_clients.count(), "returning": len(returning_ids),
        "repeat": pct(len(returning_ids), len(booked_client_ids)),
        "value": booking_value / len(booked_client_ids) if booked_client_ids else Decimal("0"),
        "referral": pct(referral_clients, period_clients.count()),
        "spend": net_spend / paying_clients if paying_clients else Decimal("0"),
        "response": average_response_hours, "conversion": pct(won_leads, period_leads.count()),
    }
    metric_specs = (
        ("New clients", "new", lambda v: f"{v:,}", "bi-person-plus", "Client records created in the selected period.", urls["clients"]),
        ("Returning clients", "returning", lambda v: f"{v:,}", "bi-person-check", "Clients booked in this period who also had an earlier confirmed booking.", urls["clients"]),
        ("Repeat booking rate", "repeat", lambda v: f"{v:.1f}%", "bi-arrow-repeat", "Returning booked clients divided by all distinct booked clients in this period.", urls["clients"]),
        ("Average client value", "value", money, "bi-gem", "Recorded booking value divided by distinct booked clients in this period.", urls["clients"]),
        ("Referral rate", "referral", lambda v: f"{v:.1f}%", "bi-share", "New client records whose converted lead source contains referral, divided by new clients.", urls["leads"] + "?source=Referral"),
        ("Average client spend", "spend", money, "bi-wallet2", "Completed payments less refunds divided by clients who paid in this period.", urls["clients"]),
        ("Lead response time", "response", lambda v: "—" if v is None else (f"{v:.1f} hrs" if v < 48 else f"{v / 24:.1f} days"), "bi-stopwatch", "Average time from lead creation to its recorded contact timestamp.", urls["leads"]),
        ("Lead-to-booking conversion", "conversion", lambda v: f"{v:.1f}%", "bi-funnel", "Leads created in this period currently marked booked, divided by all leads created.", urls["leads"] + "?status=booked"),
    )
    metrics = [{"label": label, "value": formatter(metric_values[key]), "icon": icon,
                "tooltip": tip, "url": url} for label, key, formatter, icon, tip, url in metric_specs]

    acquisition_rows = in_period(clients, "created_at").annotate(bucket=TruncWeek("created_at")).values("bucket").annotate(value=Count("pk")).order_by("bucket")
    acquisition = [{"label": _short_date(row["bucket"]), "value": row["value"]} for row in acquisition_rows]
    source_rows = period_leads.values("lead_source").annotate(total=Count("pk"), booked=Count("pk", filter=Q(status=Lead.Status.BOOKED))).order_by("-total", "lead_source")
    sources = [{"label": row["lead_source"] or "Unspecified", "value": row["total"], "booked": row["booked"],
                "conversion": float(pct(row["booked"], row["total"])),
                "url": urls["leads"] + (f"?{urlencode({'source': row['lead_source']})}" if row["lead_source"] else "")}
               for row in source_rows[:8]]
    location_rows = period_bookings.values("location").annotate(value=Count("pk")).order_by("-value", "location")
    locations = [{"label": row["location"] or "Unspecified", "value": row["value"]} for row in location_rows[:7]]

    client_revenue = {row["invoice__client_id"]: row["value"] or Decimal("0") for row in period_payments.values("invoice__client_id").annotate(value=Sum("amount"))}
    for row in period_refunds.values("payment__invoice__client_id").annotate(value=Sum("amount")):
        client_id = row["payment__invoice__client_id"]
        client_revenue[client_id] = client_revenue.get(client_id, Decimal("0")) - (row["value"] or Decimal("0"))
    client_services = {}
    for client_id, service in period_bookings.values_list("client_id", "session_type"):
        client_services.setdefault(client_id, set()).add((service or "").lower())
    all_segment_ids = set(period_clients.values_list("pk", flat=True)) | booked_client_ids | set(client_revenue)
    referral_ids = set(clients.filter(pk__in=all_segment_ids, converted_lead__lead_source__icontains="referr").values_list("pk", flat=True))
    segment_defs = [
        ("New clients", set(period_clients.values_list("pk", flat=True))), ("Returning clients", returning_ids),
        ("Referral clients", referral_ids),
        ("Wedding clients", {pk for pk, names in client_services.items() if any("wedding" in name for name in names)}),
        ("Portrait clients", {pk for pk, names in client_services.items() if any("portrait" in name for name in names)}),
        ("Corporate clients", {pk for pk, names in client_services.items() if any(word in name for name in names for word in ("corporate", "brand"))}),
    ]
    revenue_values = sorted((client_revenue.get(pk, Decimal("0")) for pk in all_segment_ids), reverse=True)
    high_value_floor = revenue_values[max(0, len(revenue_values) // 4 - 1)] if revenue_values else Decimal("0")
    segment_defs.append(("High-value clients", {pk for pk in all_segment_ids if high_value_floor and client_revenue.get(pk, 0) >= high_value_floor}))
    segments = []
    for label, ids in segment_defs:
        revenue = sum((client_revenue.get(pk, Decimal("0")) for pk in ids), Decimal("0"))
        repeats = len(ids & returning_ids)
        lead_ids = period_leads.filter(converted_client__pk__in=ids)
        lead_total, converted = lead_ids.count(), lead_ids.filter(status=Lead.Status.BOOKED).count()
        segments.append({"label": label, "clients": len(ids), "revenue": money(revenue),
                         "raw_revenue": float(revenue), "average": money(revenue / len(ids) if ids else 0),
                         "repeat": f"{pct(repeats, len(ids)):.1f}%", "conversion": f"{pct(converted, lead_total):.1f}%",
                         "trend": "—", "url": urls["clients"]})
    segments.sort(key=lambda row: row["raw_revenue"], reverse=True)

    referral_sources = [row for row in sources if "referr" in row["label"].lower()]
    return {"metrics": metrics, "new_count": len(new_booked_ids), "returning_count": len(returning_ids),
            "new_percent": float(pct(len(new_booked_ids), len(booked_client_ids))), "acquisition": acquisition,
            "sources": sources, "locations": locations, "segments": segments, "referrals": referral_sources,
            "funnel": [{"label": "Booked clients", "value": len(booked_client_ids)},
                       {"label": "Returning clients", "value": len(returning_ids)},
                       {"label": "Booked again in period", "value": period_bookings.filter(client_id__in=returning_ids).count()}],
            "urls": urls, "has_data": bool(period_clients or period_leads or period_bookings)}


def _booking_intelligence(start, end, sessions, leads, profile, currency, urls):
    """Summarize booking demand without inventing calendar or attendance data."""
    scheduled = sessions.filter(starts_at__date__range=(start, end))
    completed = scheduled.filter(status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED))
    total = scheduled.count()
    confirmed = completed.count()
    cancelled = scheduled.filter(status=ClientSession.Status.CANCELLED).count()
    period_leads = leads.filter(created_at__date__range=(start, end))
    converted = period_leads.filter(status=Lead.Status.BOOKED).count()

    def pct(value, denominator):
        return Decimal(value * 100) / denominator if denominator else Decimal("0")

    value = completed.aggregate(value=Sum("booking_value"))["value"] or Decimal("0")
    lead_times = []
    for created_at, confirmed_at in completed.exclude(confirmed_at=None).filter(
            client__converted_lead__isnull=False).values_list("client__converted_lead__created_at", "confirmed_at"):
        lead_times.append(max(0, (confirmed_at - created_at).total_seconds() / 86400))
    average_lead = sum(lead_times) / len(lead_times) if lead_times else None
    unavailable = "Not tracked"
    metric_specs = [
        ("Total bookings", f"{confirmed:,}", "Confirmed or completed bookings scheduled in this period."),
        ("Booking conversion rate", f"{pct(converted, period_leads.count()):.1f}%", "Leads created in this period currently marked booked."),
        ("Cancellation rate", f"{pct(cancelled, total):.1f}%", "Cancelled bookings divided by all bookings scheduled in this period."),
        ("Reschedule rate", unavailable, "Reschedule history is not recorded by the current booking model."),
        ("Average lead-to-book time", f"{average_lead:.1f} days" if average_lead is not None else "No linked data", "Time from a linked lead being created to its booking being confirmed."),
        ("Average booking value", _money(value / confirmed if confirmed else 0, currency), "Recorded booking value divided by confirmed and completed bookings."),
        ("Schedule utilization", unavailable, "Available working hours are not configured, so utilization cannot be calculated reliably."),
        ("No-show rate", unavailable, "No-show attendance outcomes are not recorded by the current booking model."),
    ]
    metrics = [{"label": label, "value": display, "tooltip": tip} for label, display, tip in metric_specs]

    def rows(field, labeler=lambda value: value or "Unspecified", queryset=scheduled):
        result = queryset.values(field).annotate(value=Count("pk")).order_by(field)
        return [{"label": labeler(row[field]), "value": row["value"]} for row in result]

    weekly = scheduled.annotate(bucket=TruncWeek("starts_at")).values("bucket").annotate(value=Count("pk")).order_by("bucket")
    over_time = [{"label": _short_date(row["bucket"]), "value": row["value"]} for row in weekly]
    weekdays = rows("starts_at__week_day", lambda day: ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")[day - 1])
    hour_rows = rows("starts_at__hour", lambda hour: "Morning" if hour < 12 else "Afternoon" if hour < 17 else "Evening")
    time_totals = {}
    for row in hour_rows: time_totals[row["label"]] = time_totals.get(row["label"], 0) + row["value"]
    times = [{"label": label, "value": time_totals.get(label, 0)} for label in ("Morning", "Afternoon", "Evening")]
    months = scheduled.annotate(bucket=TruncMonth("starts_at")).values("bucket").annotate(value=Count("pk")).order_by("bucket")
    seasonality = [{"label": row["bucket"].strftime("%b %Y"), "value": row["value"]} for row in months]
    statuses = [{"label": dict(ClientSession.Status.choices).get(row["status"], row["status"]), "value": row["value"]}
                for row in scheduled.values("status").annotate(value=Count("pk")).order_by("status")]
    trends = []
    for row in scheduled.annotate(bucket=TruncWeek("starts_at")).values("bucket").annotate(
            cancelled=Count("pk", filter=Q(status=ClientSession.Status.CANCELLED))).order_by("bucket"):
        trends.append({"label": _short_date(row["bucket"]), "value": row["cancelled"], "secondary": None})

    package_lines = InvoiceLineItem.objects.filter(invoice__photographer=profile,
        invoice__booking__in=scheduled, item_type=InvoiceLineItem.ItemType.PACKAGE)
    package_rows = package_lines.values("description").annotate(value=Count("invoice__booking", distinct=True)).order_by("-value")
    packages = [{"label": row["description"] or "Unspecified", "value": row["value"]} for row in package_rows]

    service_rows = scheduled.values("session_type").annotate(
        bookings=Count("pk"), revenue=Sum("booking_value"),
        cancelled=Count("pk", filter=Q(status=ClientSession.Status.CANCELLED))).order_by("-bookings", "session_type")
    services = []
    for row in service_rows:
        service_leads = period_leads.filter(event_type=row["session_type"])
        prior = sessions.filter(session_type=row["session_type"], starts_at__date__lt=start,
                                starts_at__date__gte=start - (end - start + timedelta(days=1))).count()
        bookings, revenue = row["bookings"], row["revenue"] or Decimal("0")
        trend = bookings - prior
        services.append({"service": row["session_type"] or "Unspecified", "bookings": bookings,
            "revenue": _money(revenue, currency), "average": _money(revenue / bookings if bookings else 0, currency),
            "cancellation": f"{pct(row['cancelled'], bookings):.1f}%",
            "conversion": f"{pct(service_leads.filter(status=Lead.Status.BOOKED).count(), service_leads.count()):.1f}%" if service_leads.exists() else "No lead data",
            "trend": f"{trend:+d}", "tone": "up" if trend > 0 else "down" if trend < 0 else "flat",
            "url": f"{urls['bookings']}?{urlencode({'service': row['session_type']})}"})

    heatmap = []
    heat_counts = {(row["starts_at__week_day"], row["starts_at__hour"]): row["value"] for row in
        scheduled.values("starts_at__week_day", "starts_at__hour").annotate(value=Count("pk"))}
    maximum = max(heat_counts.values(), default=1)
    for day, name in enumerate(("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"), 1):
        cells = []
        for hour, label in ((8, "8am"), (10, "10am"), (12, "12pm"), (14, "2pm"), (16, "4pm"), (18, "6pm")):
            count = sum(heat_counts.get((day, candidate), 0) for candidate in range(hour, hour + 2))
            cells.append({"label": label, "value": count, "level": round(count * 4 / maximum) if count else 0})
        heatmap.append({"label": name, "cells": cells})
    charts = [("Bookings over time", over_time), ("Bookings by service", rows("session_type")),
              ("Bookings by package", packages), ("Bookings by weekday", weekdays),
              ("Bookings by time of day", times), ("Booking seasonality", seasonality),
              ("Cancellation and reschedule trends", trends), ("Booking status distribution", statuses)]
    return {"metrics": metrics, "charts": charts, "heatmap": heatmap, "services": services,
            "has_data": bool(total), "urls": urls, "groupings": ("Location", "Team member"),
            "locations": rows("location"), "team_note": "Team-member grouping will populate when booking assignments are available."}


def _revenue_intelligence(start, end, grouping, sessions, payments, refunds, profile, currency, urls):
    """Analyze recorded revenue dimensions without inventing costs or profitability."""
    paid = payments.filter(paid_at__date__gte=start, paid_at__date__lte=end)
    returned = refunds.filter(refunded_at__date__gte=start, refunded_at__date__lte=end)
    gross = paid.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    fees = paid.aggregate(v=Sum("processor_fee"))["v"] or Decimal("0")
    refunded = returned.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    net = gross - refunded - fees
    booking_ids = set(paid.exclude(invoice__booking_id=None).values_list("invoice__booking_id", flat=True))
    client_count = paid.values("invoice__client_id").distinct().count()
    booked_period = sessions.filter(confirmed_at__date__gte=start, confirmed_at__date__lte=end,
        status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED))
    booking_count = len(booking_ids)
    booking_value = booked_period.aggregate(v=Sum("booking_value"))["v"] or Decimal("0")
    booking_total = booked_period.count()

    invoices = ClientInvoice.objects.for_photographer(profile).exclude(status=ClientInvoice.Status.VOID)
    period_invoices = invoices.filter(issue_date__gte=start, issue_date__lte=end)
    outstanding = sum((invoice.balance for invoice in period_invoices), Decimal("0"))
    collection_days = [(payment.paid_at.date() - payment.invoice.issue_date).days
                       for payment in paid.select_related("invoice")]
    average_days = sum(collection_days) / len(collection_days) if collection_days else None
    refund_rate = refunded * 100 / gross if gross else Decimal("0")
    tx = urls["transactions"]
    money = lambda value: _money(value, currency)
    metrics = [
        ("Gross revenue", money(gross), "bi-cash-stack", "Completed payments before refunds and recorded processor fees.", tx + "?record=payment"),
        ("Net revenue", money(net), "bi-wallet2", "Gross revenue less completed refunds and recorded processor fees only.", tx),
        ("Average booking value", money(booking_value / booking_total if booking_total else 0), "bi-receipt", "Recorded booking value divided by confirmed and completed bookings.", urls["bookings"]),
        ("Revenue per client", money((gross - refunded) / client_count if client_count else 0), "bi-person", "Collected revenue less refunds divided by paying clients.", tx),
        ("Revenue per booking", money((gross - refunded) / booking_count if booking_count else 0), "bi-calendar2-check", "Collected revenue less refunds divided by bookings linked to payments.", tx),
        ("Outstanding balance trend", money(outstanding), "bi-hourglass-split", "Current balance on non-void invoices issued in the selected period.", tx + "?status=outstanding"),
        ("Payment collection time", "—" if average_days is None else f"{average_days:.1f} days", "bi-stopwatch", "Average days from invoice issue to completed payment.", tx + "?record=payment"),
        ("Refund rate", f"{refund_rate:.1f}%", "bi-arrow-counterclockwise", "Completed refunds divided by gross completed payments.", tx + "?record=refund"),
    ]

    def grouped(title, field, description, limit=8):
        rows = paid.values(field).annotate(value=Sum("amount"), count=Count("pk")).order_by("-value")[:limit]
        return {"title": title, "description": description,
                "rows": [{"label": row[field] or "Unspecified", "value": money(row["value"] or 0),
                          "raw": float(row["value"] or 0), "count": row["count"], "url": tx} for row in rows]}

    service = grouped("Revenue by service", "invoice__booking__session_type", "Collected payments grouped by linked booking service.")
    location = grouped("Revenue by location", "invoice__booking__location", "Collected payments grouped by linked booking location.")
    source = grouped("Revenue by lead source", "invoice__client__converted_lead__lead_source", "Collected payments grouped by recorded lead source.")
    reports = [service]
    package_rows = InvoiceLineItem.objects.filter(invoice__photographer=profile, invoice__issue_date__gte=start,
        invoice__issue_date__lte=end, invoice__status__in=(ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID, ClientInvoice.Status.PAID),
        item_type=InvoiceLineItem.ItemType.PACKAGE).values("description").annotate(value=Sum("total"), count=Count("pk")).order_by("-value")[:8]
    reports.append({"title": "Revenue by package", "description": "Invoiced package line value; this is not presented as collected cash.",
        "rows": [{"label": row["description"] or "Unspecified", "value": money(row["value"] or 0), "raw": float(row["value"] or 0), "count": row["count"], "url": tx} for row in package_rows]})
    reports.extend([location, {"title": "Revenue by photographer or team member", "description": "Owner-level revenue is shown because booking assignments are unavailable.",
        "rows": [{"label": str(profile), "value": money(gross), "raw": float(gross), "count": paid.count(), "url": tx}] if paid.exists() else []}, source,
        grouped("Revenue by client type", "invoice__client__client_type", "Collected payments grouped by client type."),
        grouped("Revenue by booking status", "invoice__booking__status", "Collected payments grouped by current booking status.")])
    trunc = {"daily": TruncDay, "weekly": TruncWeek, "monthly": TruncMonth}[grouping]
    time_rows = paid.annotate(bucket=trunc("paid_at")).values("bucket").annotate(value=Sum("amount"), count=Count("pk")).order_by("bucket")
    time_report = {"title": "Revenue by month or season", "description": "Collected payments grouped by calendar period.",
        "rows": [{"label": row["bucket"].strftime("%b %Y"), "value": money(row["value"] or 0), "raw": float(row["value"] or 0), "count": row["count"], "url": tx} for row in time_rows]}
    reports.append(time_report)
    charts = [("Revenue trend", time_report["rows"]), ("Revenue mix by service", service["rows"]),
        ("Revenue by lead source", source["rows"]), ("Revenue by location", location["rows"]),
        ("Revenue by team member", reports[3]["rows"]),
        ("Average booking value trend", [{"label": "Selected period", "value": money(booking_value / booking_total if booking_total else 0), "raw": float(booking_value / booking_total) if booking_total else 0}]),
        ("Outstanding balance trend", [{"label": "Selected period", "value": money(outstanding), "raw": float(outstanding)}])]
    concentration = list(paid.values("invoice__client_id").annotate(value=Sum("amount")).order_by("-value"))
    top_share = concentration[0]["value"] * 100 / gross if concentration and gross else 0
    charts.append(("Revenue concentration", [{"label": "Largest client share", "value": f"{top_share:.1f}%", "raw": float(top_share)}]))
    waterfall = None
    if gross and (refunded or fees):
        waterfall = [("Gross payments", money(gross)), ("Refunds", money(-refunded)),
                     ("Processor fees", money(-fees)), ("Net revenue", money(net))]
    return {"metrics": [{"label": a, "value": b, "icon": c, "tooltip": d, "url": e} for a, b, c, d, e in metrics],
            "reports": reports, "charts": [{"title": title, "rows": rows[:8]} for title, rows in charts],
            "waterfall": waterfall, "financial_url": urls["financial"], "transactions_url": tx}


def _gallery_experience(start, end, galleries, events, sessions, profile, urls):
    """Build owner-scoped gallery reporting without exposing visitor or invitation PII."""
    period_events = events.filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
    view_events = period_events.filter(event_type=GalleryAnalyticsEvent.EventType.VIEW)
    gallery_ids = galleries.values_list("pk", flat=True)
    invitations = GalleryInvitation.objects.filter(gallery_id__in=gallery_ids,
        invited_at__date__gte=start, invited_at__date__lte=end)
    orders = GalleryOrder.objects.filter(photographer=profile, gallery_id__in=gallery_ids,
        created_at__date__gte=start, created_at__date__lte=end).exclude(
        payment_status__in=(GalleryOrder.Status.CANCELLED, GalleryOrder.Status.REFUNDED))

    views = view_events.count()
    visitors = view_events.exclude(visitor_identifier="").values("visitor_identifier").distinct().count()
    favorites = period_events.filter(event_type=GalleryAnalyticsEvent.EventType.FAVORITE).count()
    downloads = period_events.filter(event_type__in=(GalleryAnalyticsEvent.EventType.DOWNLOAD,
        GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD)).count()
    shares = period_events.filter(event_type=GalleryAnalyticsEvent.EventType.SHARE).count()
    engaged = favorites + downloads + shares
    engagement = engaged * 100 / views if views else 0
    accessed = invitations.filter(last_access_at__isnull=False).count()
    access_completion = accessed * 100 / invitations.count() if invitations.exists() else 0

    delivered = galleries.filter(published_at__date__gte=start, published_at__date__lte=end,
                                 event_date__isnull=False).only("event_date", "published_at")
    turnaround_days = [max(0, (gallery.published_at.date() - gallery.event_date).days) for gallery in delivered]
    average_delivery = sum(turnaround_days) / len(turnaround_days) if turnaround_days else None
    inactive_cutoff = timezone.now() - timedelta(days=90)
    inactive_ids = events.filter(occurred_at__gte=inactive_cutoff).values("gallery_id")
    expired_inactive = galleries.filter(Q(status=Gallery.Status.EXPIRED) |
        Q(expires_at__lt=timezone.now()) | ~Q(pk__in=inactive_ids)).distinct().count()

    daily = period_events.annotate(bucket=TruncDay("occurred_at")).values("bucket").annotate(
        views=Count("pk", filter=Q(event_type=GalleryAnalyticsEvent.EventType.VIEW)),
        favorites=Count("pk", filter=Q(event_type=GalleryAnalyticsEvent.EventType.FAVORITE)),
        downloads=Count("pk", filter=Q(event_type__in=(GalleryAnalyticsEvent.EventType.DOWNLOAD,
            GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD)))).order_by("bucket")
    trend = [{"label": _short_date(row["bucket"]), "views": row["views"],
              "favorites": row["favorites"], "downloads": row["downloads"]} for row in daily]

    event_rows = period_events.values("gallery_id").annotate(
        views=Count("pk", filter=Q(event_type=GalleryAnalyticsEvent.EventType.VIEW)),
        favorites=Count("pk", filter=Q(event_type=GalleryAnalyticsEvent.EventType.FAVORITE)),
        downloads=Count("pk", filter=Q(event_type__in=(GalleryAnalyticsEvent.EventType.DOWNLOAD,
            GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD))),
        shares=Count("pk", filter=Q(event_type=GalleryAnalyticsEvent.EventType.SHARE)))
    counts = {row["gallery_id"]: row for row in event_rows}
    order_counts = dict(orders.values_list("gallery_id").annotate(total=Count("pk")))
    service_by_client = {}
    for client_id, service in sessions.exclude(client_id=None).order_by("client_id", "-starts_at").values_list("client_id", "session_type"):
        service_by_client.setdefault(client_id, service or "Unspecified")
    rows = []
    for gallery in galleries.select_related("client"):
        data = counts.get(gallery.pk, {})
        gallery_views = data.get("views", 0)
        interactions = data.get("favorites", 0) + data.get("downloads", 0) + data.get("shares", 0)
        rows.append({"gallery": gallery.name, "client": gallery.client.first_name if gallery.client_id else "Private client",
            "service": service_by_client.get(gallery.client_id, "Unspecified"),
            "published": gallery.published_at, "views": gallery_views, "favorites": data.get("favorites", 0),
            "downloads": data.get("downloads", 0), "shares": data.get("shares", 0),
            "engagement": interactions * 100 / gallery_views if gallery_views else 0,
            "status": gallery.get_status_display(), "orders": order_counts.get(gallery.pk, 0),
            "url": f'{urls["galleries"]}{gallery.pk}/analytics/'})
    rows.sort(key=lambda row: (row["views"], row["engagement"]), reverse=True)
    service_rollup = {}
    for row in rows:
        item = service_rollup.setdefault(row["service"], {"label": row["service"], "views": 0, "engagement": 0})
        item["views"] += row["views"]
        item["engagement"] += row["favorites"] + row["downloads"] + row["shares"]
    services = sorted(service_rollup.values(), key=lambda item: item["engagement"], reverse=True)
    for item in services:
        item["rate"] = item["engagement"] * 100 / item["views"] if item["views"] else 0

    commerce_available = galleries.filter(store__isnull=False).exists()
    order_count = orders.count()
    metrics = [
        ("Total gallery views", f"{views:,}", "bi-eye"), ("Unique gallery visitors", f"{visitors:,}", "bi-people"),
        ("Average gallery engagement", f"{engagement:.1f}%", "bi-activity"), ("Favorites or selections", f"{favorites:,}", "bi-heart"),
        ("Downloads", f"{downloads:,}", "bi-download"), ("Shares", f"{shares:,}", "bi-share"),
        ("Store orders", f"{order_count:,}" if commerce_available else "Not available", "bi-bag-check"),
        ("Average gallery delivery time", f"{average_delivery:.1f} days" if average_delivery is not None else "No delivery data", "bi-stopwatch"),
        ("Client access completion", f"{access_completion:.1f}%", "bi-person-check"),
        ("Expired or inactive galleries", f"{expired_inactive:,}", "bi-clock-history"),
    ]
    return {"metrics": [{"label": label, "value": value, "icon": icon} for label, value, icon in metrics],
            "trend": trend, "galleries": rows[:10], "services": services[:8], "delivery": turnaround_days,
            "invitations": {"sent": invitations.count(), "accessed": accessed, "rate": access_completion},
            "commerce": {"available": commerce_available, "orders": order_count,
                         "conversion": order_count * 100 / visitors if visitors else 0},
            "raw": {"views": views, "engagement": engagement, "average_delivery": average_delivery}, "urls": urls}


def _operational_intelligence(start, end, grouping, sessions, leads, galleries, payments, profile, currency, urls):
    """Summarize observable workflow events, clearly marking unavailable milestones."""
    period_leads = leads.filter(created_at__date__gte=start, created_at__date__lte=end)
    period_sessions = sessions.filter(starts_at__date__gte=start, starts_at__date__lte=end)
    activities = ClientActivity.objects.for_photographer(profile)
    tasks = ClientTask.objects.for_photographer(profile)
    invoices = ClientInvoice.objects.for_photographer(profile).exclude(status=ClientInvoice.Status.VOID)

    def average(values):
        values = list(values)
        return sum(values) / len(values) if values else None

    def duration(value, unavailable="No recorded data"):
        if value is None:
            return unavailable
        return f"{value:.1f} hrs" if value < 48 else f"{value / 24:.1f} days"

    response = average(max(0, (contacted - created).total_seconds() / 3600)
                       for created, contacted in period_leads.exclude(last_contacted_at=None)
                       .values_list("created_at", "last_contacted_at"))
    contract = average(max(0, (signed - created).total_seconds() / 3600)
                       for created, signed in activities.filter(
                           event_type=ClientActivity.EventType.CONTRACT_SIGNED,
                           occurred_at__date__gte=start, occurred_at__date__lte=end,
                           lead__isnull=False).values_list("lead__created_at", "occurred_at"))
    booking_to_shoot = average(max(0, (shoot - booked).total_seconds() / 3600)
                               for booked, shoot in period_sessions.exclude(confirmed_at=None)
                               .values_list("confirmed_at", "starts_at"))
    delivered = galleries.filter(published_at__date__gte=start, published_at__date__lte=end,
                                 event_date__isnull=False)
    delivery = average(max(0, (published.date() - event).days * 24)
                       for event, published in delivered.values_list("event_date", "published_at"))
    payment_delays = []
    for paid_at, due_date, issue_date in payments.filter(paid_at__date__gte=start, paid_at__date__lte=end) \
            .values_list("paid_at", "invoice__due_date", "invoice__issue_date"):
        payment_delays.append((paid_at.date() - (due_date or issue_date)).days * 24)
    payment_delay = average(payment_delays)
    overdue_tasks = tasks.filter(due_date__lt=timezone.localdate()).exclude(status=ClientTask.Status.COMPLETED).count()
    late_deliveries = galleries.filter(event_date__gte=start, event_date__lte=end,
        published_at__isnull=True, event_date__lt=timezone.localdate()).count()
    missed_consultations = period_sessions.filter(session_type__icontains="consult",
        status=ClientSession.Status.CANCELLED).count()
    available_minutes = max(1, (end - start).days + 1) * 8 * 60
    used_minutes = period_sessions.exclude(status=ClientSession.Status.CANCELLED).aggregate(v=Sum("duration_minutes"))["v"] or 0
    utilization = min(100, used_minutes * 100 / available_minutes)

    metrics = [
        ("Average lead response time", duration(response), "bi-reply", "Lead creation to recorded first/last contact timestamp."),
        ("Average contract turnaround", duration(contract), "bi-file-earmark-check", "Lead creation to recorded contract-signed activity."),
        ("Average booking-to-shoot time", duration(booking_to_shoot), "bi-calendar-event", "Booking confirmation to scheduled shoot start."),
        ("Average editing turnaround", "Not tracked", "bi-magic", "Editing completion has no dedicated timestamp yet; no estimate is shown."),
        ("Average gallery delivery time", duration(delivery), "bi-images", "Event date to gallery publication timestamp."),
        ("Average invoice payment delay", duration(payment_delay), "bi-credit-card", "Invoice due date to payment; negative values indicate early payment."),
        ("Overdue workflows", f"{overdue_tasks:,}", "bi-exclamation-diamond", "Open workflow tasks whose due date has passed."),
        ("Late gallery deliveries", f"{late_deliveries:,}", "bi-clock-history", "Past-event galleries without a publication timestamp."),
        ("Missed consultations", f"{missed_consultations:,}", "bi-calendar-x", "Cancelled sessions whose service name contains consultation."),
        ("Schedule utilization", f"{utilization:.1f}%", "bi-speedometer2", "Scheduled non-cancelled minutes divided by an 8-hour daily capacity baseline."),
    ]

    leads_count = period_leads.count()
    consulted_ids = set(activities.filter(event_type=ClientActivity.EventType.CONSULTATION_SCHEDULED,
        lead__in=period_leads).values_list("lead_id", flat=True))
    booked_ids = set(period_leads.filter(status=Lead.Status.BOOKED).values_list("pk", flat=True))
    contract_ids = set(activities.filter(event_type=ClientActivity.EventType.CONTRACT_SIGNED,
        lead__in=period_leads).values_list("lead_id", flat=True))
    cohort_clients = Client.objects.for_photographer(profile).filter(converted_lead__in=period_leads)
    client_ids = set(cohort_clients.values_list("pk", flat=True))
    completed_sessions = sessions.filter(client_id__in=client_ids, status=ClientSession.Status.COMPLETED)
    completed_client_ids = set(completed_sessions.values_list("client_id", flat=True))
    edited_client_ids = set(galleries.filter(client_id__in=completed_client_ids,
        status__in=(Gallery.Status.READY, Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED,
                   Gallery.Status.ARCHIVED)).values_list("client_id", flat=True))
    delivered_client_ids = set(galleries.filter(client_id__in=client_ids,
        published_at__isnull=False).values_list("client_id", flat=True))
    paid_client_ids = set(invoices.filter(client_id__in=client_ids, status=ClientInvoice.Status.PAID)
                          .values_list("client_id", flat=True))
    stage_specs = [("Lead", leads_count), ("Consultation", len(consulted_ids)), ("Booked", len(booked_ids)),
                   ("Contract completed", len(contract_ids)), ("Shoot completed", len(completed_client_ids)),
                   ("Editing completed", len(edited_client_ids)), ("Gallery delivered", len(delivered_client_ids)),
                   ("Fully paid", len(paid_client_ids))]
    funnel = []
    prior = None
    for label, count in stage_specs:
        conversion = count * 100 / prior if prior else (100 if prior is None and count else 0)
        funnel.append({"label": label, "count": count, "conversion": conversion,
                       "dropoff": max(0, 100 - conversion) if prior is not None else 0,
                       "average": "Not timestamped"})
        prior = count
    transitions = [row for row in funnel[1:] if row["count"] or row["dropoff"]]
    bottleneck = max(transitions, key=lambda row: row["dropoff"], default=None)
    main_bottleneck = bottleneck["label"] if bottleneck else "Not enough workflow data"

    trunc = {"daily": TruncDay, "weekly": TruncWeek, "monthly": TruncMonth}[grouping]
    def trend(qs, field, value_name="value"):
        return [{"label": _short_date(row["bucket"]), "value": round(float(row[value_name] or 0), 1)}
                for row in qs.annotate(bucket=trunc(field)).values("bucket").annotate(
                    value=Count("pk")).order_by("bucket")]
    reports = [
        {"title": "Workflow bottlenecks", "description": f"Largest observed stage drop-off: {main_bottleneck}.", "rows": funnel[1:]},
        {"title": "Late or overdue work", "description": "Open overdue tasks and undelivered past-event galleries.", "stats": [("Overdue workflows", overdue_tasks), ("Late galleries", late_deliveries), ("Missed consultations", missed_consultations)]},
        {"title": "Delivery turnaround trend", "description": "Published galleries by period; exact delivery-time trend uses recorded event dates.", "trend": trend(delivered, "published_at")},
        {"title": "Lead response trend", "description": "Contacted leads by contact timestamp.", "trend": trend(period_leads.exclude(last_contacted_at=None), "last_contacted_at")},
        {"title": "Payment delay trend", "description": "Completed payments by payment date; headline metric measures delay against due dates.", "trend": trend(payments.filter(paid_at__date__gte=start, paid_at__date__lte=end), "paid_at")},
        {"title": "Team workload", "description": "Assignments are not recorded. Owner totals are shown neutrally; no ranking is produced.", "stats": [(str(profile), period_sessions.exclude(status=ClientSession.Status.CANCELLED).count())]},
        {"title": "Location performance", "description": "Completed shoots grouped by recorded booking location.", "locations": list(period_sessions.values("location").annotate(value=Count("pk"), revenue=Sum("booking_value")).order_by("-value")[:8])},
    ]
    team = {"available": False, "context": "Team-member assignments and satisfaction scores are not recorded. Comparisons remain unavailable rather than attributing owner-level work unfairly.",
            "columns": ("Shoots completed", "Revenue associated", "Average turnaround", "Workload", "Late tasks", "Client satisfaction")}
    return {"metrics": [{"label": a, "value": b, "icon": c, "tooltip": d} for a, b, c, d in metrics],
            "funnel": funnel, "main_bottleneck": main_bottleneck, "reports": reports, "team": team,
            "currency": currency, "urls": urls,
            "raw": {"overdue_tasks": overdue_tasks, "late_deliveries": late_deliveries,
                    "missed_consultations": missed_consultations, "utilization": utilization}}


def analytics_overview(profile, params, base_url, today=None):
    """Return filter choices and KPI values; every query remains owner scoped."""
    today = today or timezone.localdate()
    range_key, start, end = _window(params, today)
    compare_key = params.get("compare", "previous_period")
    if compare_key not in dict(COMPARES): compare_key = "previous_period"
    previous_start, previous_end = _comparison(compare_key, start, end)
    grouping = params.get("grouping", "daily")
    if grouping not in dict(GROUPINGS): grouping = "daily"
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
        prior_client_ids = booked.filter(confirmed_at__date__lt=a).values("client_id")
        repeat = bs.filter(client_id__in=prior_client_ids).values("client_id").distinct().count()
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

    period_invoices = ClientInvoice.objects.for_photographer(profile).filter(issue_date__gte=start, issue_date__lte=end)
    if any(selected.values()):
        period_invoices = period_invoices.filter(booking_id__in=session_ids)
    invoiced = period_invoices.exclude(status=ClientInvoice.Status.VOID).aggregate(v=Sum("total"))["v"] or Decimal("0")
    collected = InvoicePayment.objects.filter(invoice__in=period_invoices.exclude(status=ClientInvoice.Status.VOID),
                                                status=InvoicePayment.Status.COMPLETED).aggregate(v=Sum("amount"))["v"] or Decimal("0")
    payment_ratio = Decimal(collected * 100) / invoiced if invoiced else None
    scheduled = sessions.filter(starts_at__date__gte=start, starts_at__date__lte=end)
    scheduled_count = scheduled.count()
    cancellation_rate = Decimal(scheduled.filter(status=ClientSession.Status.CANCELLED).count() * 100) / scheduled_count if scheduled_count else None
    root = base_url.rsplit('/analytics/', 1)[0]
    urls = {"financial": f"{root}/financial/", "bookings": f"{root}/bookings/", "growth": f"{root}/growth/",
            "galleries": f"{root}/galleries/", "clients": f"{root}/clients/", "leads": f"{root}/leads/", "transactions": f"{root}/financial/transactions/"}
    business_health = _business_health(current, previous, payment_ratio, cancellation_rate, urls)
    currency = getattr(profile, "default_currency", "USD")
    business_trends = _business_trends(profile, start, end, (previous_start, previous_end), grouping,
        booked, clients, leads, events, payments, refunds, currency, urls)
    contributors = [item["label"] for item in business_trends.get("services", [])[:5]]
    for metric in metrics:
        metric["contributors"] = contributors
    customer_intelligence = _customer_intelligence(start, end, (previous_start, previous_end),
        booked, clients, leads, payments, refunds, currency, urls)
    booking_intelligence = _booking_intelligence(start, end, sessions, leads, profile, currency, urls)
    revenue_intelligence = _revenue_intelligence(start, end, grouping, sessions, payments, refunds, profile, currency, urls)
    gallery_experience = _gallery_experience(start, end, galleries, events, sessions, profile, urls)
    operational_intelligence = _operational_intelligence(
        start, end, grouping, sessions, leads, galleries, payments, profile, currency, urls
    )
    insights = _analytics_insights(current, previous, payment_ratio, invoiced, collected,
        cancellation_rate, customer_intelligence, gallery_experience, operational_intelligence,
        urls, currency)

    observations = []
    def add_observation(priority, tone, title, change, why, action, url):
        observations.append({"priority": priority, "tone": tone, "title": title, "change": change,
                             "why": why, "action": action, "url": url})
    if previous:
        for key, title, why, action, url in (
            ("revenue", "Revenue", "Revenue momentum affects cash available for upcoming work.", "Review revenue", urls["financial"]),
            ("conversion", "Lead conversion", "Conversion determines how efficiently inquiries become paid work.", "Review lead funnel", urls["growth"]),
            ("views", "Gallery engagement", "Engaged clients are more likely to favorite, share, and purchase.", "Review galleries", urls["galleries"]),
            ("bookings", "Bookings", "Booking momentum indicates future workload and revenue.", "Review bookings", urls["bookings"]),
        ):
            before, now = previous[key], current[key]
            if before and now != before:
                delta = (Decimal(str(now)) - Decimal(str(before))) / Decimal(str(before)) * 100
                direction = "increased" if delta > 0 else "declined"
                add_observation(3 if delta < 0 else 2, "risk" if delta < 0 else "success", f"{title} {direction}",
                                f"{title} {direction} {abs(delta):.1f}% compared with the previous period.", why, action, url)
    service_counts = period(booked, "confirmed_at", start, end).values("session_type").annotate(total=Sum("booking_value")).order_by("-total")
    if service_counts and service_counts[0]["session_type"]:
        service = service_counts[0]["session_type"]
        add_observation(1, "opportunity", f"{service} is the strongest service", f"{service} generated the most recorded booking value this period.",
                        "Knowing the strongest service helps focus marketing and capacity.", "View service bookings", urls["bookings"])
    if payment_ratio is not None and payment_ratio < 75:
        add_observation(4, "risk", "Payment collection needs attention", f"Only {payment_ratio:.1f}% of invoiced value has been collected.",
                        "Outstanding balances can constrain cash flow.", "Review outstanding invoices", urls["financial"])
    business_summary = sorted(observations, key=lambda item: item["priority"], reverse=True)[:5]

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
            "partial_message": "Net revenue excludes operating expenses because expense records are not available.",
            "business_health": business_health, "business_summary": business_summary, "business_trends": business_trends,
            "customer_intelligence": customer_intelligence, "booking_intelligence": booking_intelligence,
            "revenue_intelligence": revenue_intelligence, "gallery_experience": gallery_experience,
            "operational_intelligence": operational_intelligence, "analytics_insights": insights}
