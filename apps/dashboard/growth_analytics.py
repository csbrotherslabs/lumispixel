"""Owner-scoped selectors for the Growth Overview summary cards."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import ClientSession, Lead
from apps.dashboard.financial import format_currency

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


def _percent(numerator, denominator):
    if not denominator:
        return None
    return (Decimal(numerator) / Decimal(denominator) * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _period_values(profile, start, end):
    leads = _during(Lead.objects.for_photographer(profile), "created_at", start, end)
    eligible_leads = leads.exclude(status=Lead.Status.LOST)
    bookings = _during(ClientSession.objects.for_photographer(profile).filter(
        status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED)), "created_at", start, end)
    booking_count = bookings.count()
    booking_total = bookings.aggregate(total=Coalesce(
        Sum("booking_value"), Value(ZERO), output_field=MONEY_FIELD))["total"]
    referral_count = bookings.filter(client__converted_lead__lead_source__iregex=r"referr").count()
    repeat_count = 0
    for booking in bookings.only("client_id", "created_at"):
        if ClientSession.objects.for_photographer(profile).filter(
            client_id=booking.client_id, status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED),
            created_at__lt=booking.created_at).exists():
            repeat_count += 1
    return {"new_leads": leads.count(), "confirmed_bookings": booking_count,
            "conversion_rate": _percent(eligible_leads.filter(status=Lead.Status.BOOKED).count(), eligible_leads.count()),
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
        ("New leads", "new_leads", "Leads created during the selected period.", "New inquiries received", "photographer_workspace:leads", "count"),
        ("Confirmed bookings", "confirmed_bookings", "Bookings confirmed during the selected period.", "Confirmed and completed sessions", "photographer_workspace:bookings", "count"),
        ("Lead conversion rate", "conversion_rate", "Eligible converted leads divided by eligible leads.", "Lost leads are excluded", "photographer_workspace:leads", "rate"),
        ("Average booking value", "average_booking_value", "Total confirmed booking value divided by confirmed bookings.", "Based on confirmed booking value", "photographer_workspace:bookings", "money"),
        ("Repeat client rate", "repeat_client_rate", "Bookings from returning clients divided by eligible bookings.", "Clients with an earlier confirmed booking", "photographer_workspace:clients", "rate"),
        ("Referral bookings", "referral_bookings", "Confirmed bookings attributed to a referral lead source.", "Referral-attributed confirmations", "photographer_workspace:referrals", "count"),
    ]
    cards = []
    for title, key, tooltip, detail, url_name, kind in definitions:
        value = current[key]
        percentage, trend = _comparison(value, previous[key] if previous else None)
        formatted = "—" if value is None else (format_currency(value, currency) if kind == "money" else f"{value}%" if kind == "rate" else f"{value:,}")
        cards.append({"title": title, "value": value, "formatted_value": formatted, "percentage": percentage,
                      "trend": trend, "period_label": window.label, "tooltip": tooltip,
                      "supporting_value": detail, "url": reverse(url_name)})
    return {"cards": cards, "values": current, "window": window}
