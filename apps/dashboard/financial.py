"""Database-backed selectors for the Financial Overview.

Money concepts intentionally remain separate: invoice value is billed value, payments
are cash receipts, refunds are cash outflows, credits are non-cash adjustments, and
booking value is the value agreed for confirmed sessions.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from apps.clients.models import ClientInvoice, ClientSession, InvoiceCredit, InvoicePayment, PaymentRefund

ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def format_currency(value, currency="USD"):
    if value is None:
        return "—"
    amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    prefix = {"USD": "$", "CAD": "CA$", "AUD": "A$", "GBP": "£", "EUR": "€"}.get(currency, f"{currency} ")
    return f"{'-' if amount < ZERO else ''}{prefix}{abs(amount):,.2f}"


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
        elapsed = (today - start).days
        previous_start = _shift_month(start, -3)
        return DateWindow(start, today, previous_start, previous_start + timedelta(days=elapsed), "vs previous quarter")
    if range_key == "this_year":
        start = date(today.year, 1, 1)
        prior_day = min(today.day, monthrange(today.year - 1, today.month)[1])
        return DateWindow(start, today, date(today.year - 1, 1, 1), date(today.year - 1, today.month, prior_day), "vs previous year")
    if range_key == "all_time":
        return DateWindow(None, today, None, None, "all-time total")
    start = today.replace(day=1)
    previous_end = start - timedelta(days=1)
    # Compare equal elapsed days, rather than a partial month to a complete month.
    previous_start = previous_end.replace(day=1)
    previous_end = min(previous_start + timedelta(days=(today - start).days), previous_end)
    return DateWindow(start, today, previous_start, previous_end, "vs previous month")


def _dated(queryset, field, start, end):
    filters = {f"{field}__date__lte": end}
    if start:
        filters[f"{field}__date__gte"] = start
    return queryset.filter(**filters)


def scoped_financial_records(profile, start, end, today=None):
    """Return all overview values in a bounded number of owner-scoped queries."""
    today = today or timezone.localdate()
    invoices = ClientInvoice.objects.for_photographer(profile).exclude(status__in=(ClientInvoice.Status.VOID, ClientInvoice.Status.DRAFT))
    period_invoices = _dated(invoices, "created_at", start, end)
    payment_subquery = (InvoicePayment.objects.filter(invoice_id=OuterRef("pk"), photographer=profile, status=InvoicePayment.Status.COMPLETED)
                        .values("invoice_id").annotate(value=Sum("amount")).values("value"))
    credit_subquery = (InvoiceCredit.objects.filter(invoice_id=OuterRef("pk"), photographer=profile, status=InvoiceCredit.Status.APPLIED)
                       .values("invoice_id").annotate(value=Sum("amount")).values("value"))
    invoice_rows = period_invoices.annotate(
        payment_total=Coalesce(Subquery(payment_subquery, output_field=MONEY_FIELD), Value(ZERO), output_field=MONEY_FIELD),
        credit_total=Coalesce(Subquery(credit_subquery, output_field=MONEY_FIELD), Value(ZERO), output_field=MONEY_FIELD),
    ).annotate(
        effective_paid=Greatest(F("amount_paid"), F("payment_total")),
        balance=Greatest(Value(ZERO), F("total") - Greatest(F("amount_paid"), F("payment_total")) - F("credit_total")),
    )
    invoice_values = invoice_rows.aggregate(
        invoice_value=Coalesce(Sum("total"), Value(ZERO), output_field=MONEY_FIELD),
        outstanding=Coalesce(Sum("balance"), Value(ZERO), output_field=MONEY_FIELD),
    )
    overdue = invoice_rows.filter(due_date__lt=today).exclude(status=ClientInvoice.Status.PAID).aggregate(
        value=Coalesce(Sum("balance"), Value(ZERO), output_field=MONEY_FIELD)
    )["value"]
    payments = _dated(InvoicePayment.objects.for_photographer(profile).filter(status=InvoicePayment.Status.COMPLETED), "paid_at", start, end)
    payment_total = payments.aggregate(value=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY_FIELD))["value"]
    # amount_paid is retained as a legacy cash record only when no first-class payment exists.
    legacy_cash = period_invoices.filter(amount_paid__gt=ZERO, payments__isnull=True).aggregate(
        value=Coalesce(Sum("amount_paid"), Value(ZERO), output_field=MONEY_FIELD)
    )["value"]
    refunds = _dated(PaymentRefund.objects.for_photographer(profile).filter(status=PaymentRefund.Status.COMPLETED), "refunded_at", start, end)
    refund_total = refunds.aggregate(value=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY_FIELD))["value"]
    credits = _dated(InvoiceCredit.objects.for_photographer(profile).filter(status=InvoiceCredit.Status.APPLIED), "applied_at", start, end)
    credit_total = credits.aggregate(value=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY_FIELD))["value"]
    bookings = ClientSession.objects.for_photographer(profile).filter(status__in=(ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED), starts_at__date__lte=end)
    if start:
        bookings = bookings.filter(starts_at__date__gte=start)
    booking_total = bookings.aggregate(value=Coalesce(Sum("booking_value"), Value(ZERO), output_field=MONEY_FIELD))["value"]
    collected = payment_total + legacy_cash
    return {**invoice_values, "collected": collected, "refunds": refund_total, "credits": credit_total,
            "net_revenue": collected - refund_total, "overdue": overdue, "booking_value": booking_total,
            "has_activity": period_invoices.exists() or payments.exists() or refunds.exists() or credits.exists() or bookings.exists()}


def _comparison(current, previous):
    if previous is None or previous == ZERO:
        return None, "neutral"
    percentage = ((current - previous) / abs(previous) * Decimal("100")).quantize(Decimal("0.1"))
    return percentage, "positive" if percentage > 0 else "negative" if percentage < 0 else "neutral"


def financial_summary(profile, range_key, currency="USD", today=None):
    window = date_window(range_key, today)
    current = scoped_financial_records(profile, window.start, window.end, today)
    previous = scoped_financial_records(profile, window.previous_start, window.previous_end, today) if window.previous_end else None
    definitions = [
        ("Total revenue", "net_revenue", "Completed cash payments less completed cash refunds."),
        ("Payments collected", "collected", "Gross completed cash payments received in this period."),
        ("Outstanding balance", "outstanding", "Unpaid invoice value after payments and applied credits."),
        ("Overdue balance", "overdue", "Outstanding non-draft invoice balances past their due date."),
        ("Refunds", "refunds", "Completed cash refunds issued in this period."),
        ("Total booking value", "booking_value", "Value of confirmed or completed bookings scheduled in this period."),
    ]
    cards = []
    for title, key, tooltip in definitions:
        value = current[key]
        percentage, trend = _comparison(value, previous[key] if previous else None)
        cards.append({"title": title, "value": value, "formatted_value": format_currency(value, currency), "percentage": percentage,
                      "trend": trend, "period_label": window.label, "tooltip": tooltip, "supporting_value": None})
    return {"cards": cards, "has_activity": current["has_activity"], "window": window, "values": current}
