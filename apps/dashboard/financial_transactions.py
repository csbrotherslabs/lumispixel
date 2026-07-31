"""Display-ready records for the unified financial transactions table."""
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import ClientInvoice, ClientSession, InvoiceCredit, InvoicePayment, PaymentRefund
from apps.dashboard.financial import date_window, format_currency

PAGE_SIZES = (10, 25, 50, 100)
SORTS = {
    "date": lambda row: row["date"],
    "amount": lambda row: row["sort_amount"],
    "client": lambda row: row["client"].casefold(),
    "reference": lambda row: row["reference"],
    "status": lambda row: row["status_label"].casefold(),
}


def _decimal(value):
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


def _base_row(kind, item, invoice, occurred_at, amount, currency, booking):
    client = invoice.client
    references = {"invoice": "INV", "payment": "PAY", "refund": "REF", "credit": "CRD"}
    icons = {"invoice": "bi-receipt", "payment": "bi-credit-card", "refund": "bi-arrow-counterclockwise", "credit": "bi-wallet2"}
    descriptions = {"invoice": "Client invoice", "payment": f"Payment for INV-{invoice.pk:06d}",
                    "credit": f"Credit for INV-{invoice.pk:06d}"}
    description = f"Refund for PAY-{item.payment_id:06d}" if kind == "refund" else descriptions[kind]
    return {
        "id": f"{kind}-{item.pk}", "type": kind, "type_label": kind.title(), "icon": icons[kind],
        "reference": f"{references[kind]}-{item.pk:06d}", "client": str(client),
        "client_url": reverse("photographer_workspace:client_detail", args=[client.pk]),
        "booking": booking.session_type if booking else "", "booking_url": reverse("photographer_workspace:booking_detail", args=[booking.pk]) if booking else "",
        "description": description, "date": occurred_at, "sort_amount": amount,
        "record_url": f"{reverse('photographer_workspace:transactions')}?{kind}={item.pk}",
        "gross": format_currency(amount, currency), "fee": "—", "net": "—", "method": "—",
    }


def transaction_records(profile, filters, view_key, page_number=1, page_size=25, sort="date", direction="desc", currency="USD"):
    """Return an owner-scoped, filtered and server-paginated unified record list."""
    window = date_window(filters.get("range") or "this_month")
    bookings = ClientSession.objects.for_photographer(profile).exclude(status=ClientSession.Status.CANCELLED).order_by("-starts_at")
    prefetch = Prefetch("client__sessions", queryset=bookings, to_attr="transaction_bookings")
    invoices = ClientInvoice.objects.for_photographer(profile).select_related("client").prefetch_related(prefetch)
    payments = InvoicePayment.objects.for_photographer(profile).select_related("invoice__client").prefetch_related(
        Prefetch("invoice__client__sessions", queryset=bookings, to_attr="transaction_bookings"))
    refunds = PaymentRefund.objects.for_photographer(profile).select_related("payment__invoice__client").prefetch_related(
        Prefetch("payment__invoice__client__sessions", queryset=bookings, to_attr="transaction_bookings"))
    credits = InvoiceCredit.objects.for_photographer(profile).select_related("invoice__client").prefetch_related(
        Prefetch("invoice__client__sessions", queryset=bookings, to_attr="transaction_bookings"))

    query, client, booking = filters.get("q", ""), filters.get("client", ""), filters.get("booking", "")
    if client:
        client_q = Q(client__first_name__icontains=client) | Q(client__last_name__icontains=client) | Q(client__email__icontains=client)
        invoices = invoices.filter(client_q)
        payments = payments.filter(Q(invoice__client__first_name__icontains=client) | Q(invoice__client__last_name__icontains=client) | Q(invoice__client__email__icontains=client))
        refunds = refunds.filter(Q(payment__invoice__client__first_name__icontains=client) | Q(payment__invoice__client__last_name__icontains=client) | Q(payment__invoice__client__email__icontains=client))
        credits = credits.filter(Q(invoice__client__first_name__icontains=client) | Q(invoice__client__last_name__icontains=client) | Q(invoice__client__email__icontains=client))
    if booking:
        invoices = invoices.filter(client__sessions__session_type__icontains=booking).distinct()
        payments = payments.filter(invoice__client__sessions__session_type__icontains=booking).distinct()
        refunds = refunds.filter(payment__invoice__client__sessions__session_type__icontains=booking).distinct()
        credits = credits.filter(invoice__client__sessions__session_type__icontains=booking).distinct()

    dated = (("invoice", invoices, "created_at"), ("payment", payments, "paid_at"), ("refund", refunds, "refunded_at"), ("credit", credits, "applied_at"))
    rows = []
    selected_type = filters.get("record_type") or ({"invoices": "invoice", "payments": "payment", "refunds": "refund", "credits": "credit"}.get(view_key))
    minimum, maximum = _decimal(filters.get("amount_min")), _decimal(filters.get("amount_max"))
    today = timezone.localdate()
    for kind, queryset, date_field in dated:
        if selected_type and kind != selected_type:
            continue
        if window.start:
            queryset = queryset.filter(**{f"{date_field}__date__gte": window.start})
        queryset = queryset.filter(**{f"{date_field}__date__lte": window.end})
        for item in queryset:
            invoice = item if kind == "invoice" else item.payment.invoice if kind == "refund" else item.invoice
            amount = item.total if kind == "invoice" else item.amount
            status = item.status
            status_label = item.get_status_display()
            if kind == "invoice" and invoice.due_date and invoice.due_date < today and status not in (ClientInvoice.Status.PAID, ClientInvoice.Status.VOID):
                status, status_label = "overdue", "Overdue"
            if view_key == "overdue" and status != "overdue":
                continue
            if filters.get("status") and filters["status"] != status:
                continue
            if minimum is not None and amount < minimum or maximum is not None and amount > maximum:
                continue
            booking_item = invoice.client.transaction_bookings[0] if invoice.client.transaction_bookings else None
            row = _base_row(kind, item, invoice, getattr(item, date_field), -amount if kind == "refund" else amount, currency, booking_item)
            row.update({"status": status, "status_label": status_label})
            searchable = " ".join((row["reference"], row["client"], row["booking"], row["description"], row["gross"])).casefold()
            if query and query.casefold() not in searchable:
                continue
            # Method/source metadata is not yet recorded by these models; an explicit filter cannot match it.
            if filters.get("payment_method") or filters.get("source"):
                continue
            if kind == "invoice":
                row["net"] = format_currency(invoice.balance, currency)
                row["net_label"] = "Balance"
            elif kind == "payment":
                row["net"] = format_currency(amount, currency)
                row["net_label"] = "Net"
            elif kind == "refund":
                row["gross"] = format_currency(-amount, currency)
                row["net"] = format_currency(-amount, currency)
                row["net_label"] = "Net"
            else:
                remaining = amount if status == InvoiceCredit.Status.DRAFT else Decimal("0.00")
                row["net"] = format_currency(remaining, currency)
                row["net_label"] = "Remaining"
            rows.append(row)

    sort = sort if sort in SORTS else "date"
    direction = direction if direction in {"asc", "desc"} else "desc"
    rows.sort(key=SORTS[sort], reverse=direction == "desc")
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 25
    page_size = page_size if page_size in PAGE_SIZES else 25
    page = Paginator(rows, page_size).get_page(page_number)
    return {"page": page, "rows": page.object_list, "page_size": page_size, "page_sizes": PAGE_SIZES,
            "sort": sort, "direction": direction, "total": len(rows)}
