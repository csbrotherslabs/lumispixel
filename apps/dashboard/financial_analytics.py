"""Server-side aggregation for the Financial Overview analytics panels."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.clients.models import ClientInvoice
from apps.dashboard.financial import ZERO, date_window, format_currency

MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _invoice_scope(profile, start, end):
    invoices = ClientInvoice.objects.for_photographer(profile).exclude(status=ClientInvoice.Status.VOID)
    if start:
        invoices = invoices.filter(created_at__date__gte=start)
    return invoices.filter(created_at__date__lte=end)


def _grouping(start, end):
    days = (end - start).days + 1
    if days <= 45:
        return "daily", TruncDate("created_at")
    if days <= 180:
        return "weekly", TruncWeek("created_at")
    return "monthly", TruncMonth("created_at")


def _advance(day, grouping):
    if grouping == "daily":
        return day + timedelta(days=1)
    if grouping == "weekly":
        return day + timedelta(days=7)
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def _bucket_start(day, grouping):
    if grouping == "weekly":
        return day - timedelta(days=day.weekday())
    if grouping == "monthly":
        return day.replace(day=1)
    return day


def _series(profile, start, end, grouping, truncator):
    rows = (_invoice_scope(profile, start, end).annotate(bucket=truncator)
            .values("bucket").annotate(total=Coalesce(Sum("amount_paid"), Value(ZERO), output_field=MONEY_FIELD))
            .order_by("bucket"))
    values = {(row["bucket"].date() if hasattr(row["bucket"], "date") else row["bucket"]): row["total"] for row in rows}
    cursor, result = _bucket_start(start, grouping), []
    final = _bucket_start(end, grouping)
    while cursor <= final:
        result.append(values.get(cursor, ZERO))
        cursor = _advance(cursor, grouping)
    return result


def _labels(start, count, grouping):
    labels, cursor = [], _bucket_start(start, grouping)
    for _ in range(count):
        labels.append(cursor.strftime("%b %-d" if grouping != "monthly" else "%b %Y"))
        cursor = _advance(cursor, grouping)
    return labels


def _chart_points(values, maximum):
    """Return SVG-ready coordinates; templates never perform analytics math."""
    if not values:
        return ""
    step = 100 / max(len(values) - 1, 1)
    return " ".join(f"{index * step:.2f},{92 - (float(value) / float(maximum) * 78):.2f}"
                    for index, value in enumerate(values))


def _status_rows(profile, start, end, currency, today):
    invoices = _invoice_scope(profile, start, end)
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY_FIELD)
    overdue = invoices.filter(due_date__lt=today).exclude(status=ClientInvoice.Status.PAID)
    groups = [
        ("paid", "Paid", invoices.filter(status=ClientInvoice.Status.PAID), F("total")),
        ("partial", "Partially paid", invoices.filter(Q(due_date__gte=today) | Q(due_date=None), status=ClientInvoice.Status.PARTIALLY_PAID), balance),
        ("awaiting", "Awaiting payment", invoices.filter(Q(due_date__gte=today) | Q(due_date=None), status__in=(ClientInvoice.Status.DRAFT, ClientInvoice.Status.SENT)), balance),
        ("overdue", "Overdue", overdue, balance),
    ]
    raw = []
    for key, label, queryset, amount in groups:
        total = queryset.aggregate(value=Coalesce(Sum(amount), Value(ZERO), output_field=MONEY_FIELD))["value"]
        raw.append((key, label, queryset.count(), total))
    raw.append(("refunded", "Refunded or credited", 0, ZERO))
    relevant_total = sum((item[3] for item in raw), ZERO)
    return [{"key": key, "label": label, "count": count, "total": total,
             "formatted_total": format_currency(total, currency),
             "percentage": int((total / relevant_total * Decimal("100")).quantize(Decimal("1"))) if relevant_total else 0}
            for key, label, count, total in raw]


def financial_analytics(profile, range_key, currency="USD", today=None):
    """Build display-ready revenue comparison and payment-status analytics."""
    today = today or timezone.localdate()
    window = date_window(range_key, today)
    start = window.start or (_invoice_scope(profile, None, window.end).order_by("created_at")
                             .values_list("created_at__date", flat=True).first()) or today
    grouping, truncator = _grouping(start, window.end)
    current = _series(profile, start, window.end, grouping, truncator)
    previous = []
    if window.previous_start and window.previous_end:
        previous = _series(profile, window.previous_start, window.previous_end, grouping, truncator)
    maximum = max(current + previous + [Decimal("1")])
    current_total, previous_total = sum(current, ZERO), sum(previous, ZERO)
    labels = _labels(start, len(current), grouping)
    summary = (f"Revenue for the selected period totals {format_currency(current_total, currency)}. "
               + (f"The previous equivalent period totals {format_currency(previous_total, currency)}. " if previous else "No previous period comparison is available. ")
               + f"Values are grouped {grouping}.")
    return {"grouping": grouping, "labels": labels, "first_label": labels[0], "last_label": labels[-1],
            "current_points": _chart_points(current, maximum), "previous_points": _chart_points(previous, maximum),
            "current_total": format_currency(current_total, currency), "previous_total": format_currency(previous_total, currency),
            "has_revenue": any(current) or any(previous), "summary": summary,
            "statuses": _status_rows(profile, start, window.end, currency, today)}
