"""Financial overview selectors kept separate from presentation code."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.clients.models import ClientInvoice

ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def format_currency(value, currency="USD"):
    """Format money consistently without converting it to a float."""
    if value is None:
        return "—"
    amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    symbols = {"USD": "$", "CAD": "CA$", "AUD": "A$", "GBP": "£", "EUR": "€"}
    prefix = symbols.get(currency, f"{currency} ")
    sign = "-" if amount < ZERO else ""
    return f"{sign}{prefix}{abs(amount):,.2f}"


@dataclass(frozen=True)
class DateWindow:
    start: date | None
    end: date
    previous_start: date | None
    previous_end: date | None
    label: str


def _shift_month(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def date_window(range_key, today=None):
    today = today or timezone.localdate()
    if range_key == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        start, previous_end = end.replace(day=1), end.replace(day=1) - timedelta(days=1)
        return DateWindow(start, end, previous_end.replace(day=1), previous_end, "vs previous month")
    if range_key == "this_quarter":
        start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        return DateWindow(start, today, _shift_month(start, -3), start - timedelta(days=1), "vs previous quarter")
    if range_key == "this_year":
        start = date(today.year, 1, 1)
        prior_day = min(today.day, monthrange(today.year - 1, today.month)[1])
        return DateWindow(start, today, date(today.year - 1, 1, 1), date(today.year - 1, today.month, prior_day), "vs previous year")
    if range_key == "all_time":
        return DateWindow(None, today, None, None, "all-time total")
    start = today.replace(day=1)
    previous_end = start - timedelta(days=1)
    return DateWindow(start, today, previous_end.replace(day=1), previous_end, "vs previous month")


def _invoice_totals(profile, start, end):
    invoices = ClientInvoice.objects.for_photographer(profile).exclude(status=ClientInvoice.Status.VOID)
    if start:
        invoices = invoices.filter(created_at__date__gte=start)
    invoices = invoices.filter(created_at__date__lte=end)
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY_FIELD)
    values = invoices.aggregate(
        payments=Coalesce(Sum("amount_paid"), Value(ZERO), output_field=MONEY_FIELD),
        outstanding=Coalesce(Sum(balance), Value(ZERO), output_field=MONEY_FIELD),
    )
    values["overdue"] = invoices.filter(due_date__lt=timezone.localdate()).exclude(
        status=ClientInvoice.Status.PAID
    ).aggregate(total=Coalesce(Sum(balance), Value(ZERO), output_field=MONEY_FIELD))["total"]
    values["count"] = invoices.count()
    return values


def _comparison(current, previous):
    if current is None or previous is None or previous == ZERO:
        return None, "neutral"
    percentage = ((current - previous) / abs(previous) * Decimal("100")).quantize(Decimal("0.1"))
    return percentage, "positive" if percentage > 0 else "negative" if percentage < 0 else "neutral"


def financial_summary(profile, range_key, currency="USD", today=None):
    """Return display-ready, date-scoped metrics using Decimal values throughout."""
    window = date_window(range_key, today)
    current = _invoice_totals(profile, window.start, window.end)
    previous = _invoice_totals(profile, window.previous_start, window.previous_end) if window.previous_end else None
    refunds = ZERO  # Refund and credit models are not available yet.
    raw_metrics = [
        ("Total revenue", current["payments"] - refunds, "Completed payments less completed refunds.", None),
        ("Payments collected", current["payments"], "Gross completed payments received in this period.", None),
        ("Outstanding balance", current["outstanding"], "Unpaid invoice totals after recorded payments and applicable credits.", None),
        ("Overdue balance", current["overdue"], "Outstanding invoice balances past their due date.", None),
        ("Refunds", refunds, "Completed refunds issued in this period.", "Refund tracking not yet connected"),
        ("Total booking value", None, "Value of confirmed bookings in this period.", "Booking values not yet available"),
    ]
    previous_values = [previous["payments"] if previous else None, previous["payments"] if previous else None,
                       previous["outstanding"] if previous else None, previous["overdue"] if previous else None,
                       ZERO if previous else None, None]
    cards = []
    for (title, value, tooltip, supporting), previous_value in zip(raw_metrics, previous_values):
        percentage, trend = _comparison(value, previous_value)
        cards.append({"title": title, "value": value, "formatted_value": format_currency(value, currency),
                      "percentage": percentage, "trend": trend, "period_label": window.label,
                      "tooltip": tooltip, "supporting_value": supporting})
    return {"cards": cards, "has_activity": current["count"] > 0, "window": window}
