"""Owner-scoped, display-ready activity for the financial overview."""
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Prefetch
from django.urls import reverse

from apps.clients.models import ClientInvoice, ClientSession, InvoiceCredit, InvoicePayment, PaymentRefund
from apps.dashboard.financial import date_window, format_currency

ACTIVITY_LIMIT = 8
ACTIVITY_TYPES = (
    ("invoice_created", "Invoice created", "bi-receipt", "draft"),
    ("invoice_sent", "Invoice sent", "bi-send", "sent"),
    ("invoice_viewed", "Invoice viewed", "bi-eye", "viewed"),
    ("payment_received", "Payment received", "bi-check-circle", "completed"),
    ("payment_failed", "Payment failed", "bi-exclamation-circle", "failed"),
    ("refund_initiated", "Refund initiated", "bi-arrow-counterclockwise", "pending"),
    ("refund_completed", "Refund completed", "bi-arrow-counterclockwise", "completed"),
    ("credit_issued", "Credit issued", "bi-plus-circle", "completed"),
    ("invoice_voided", "Invoice voided", "bi-slash-circle", "void"),
    ("due_date_changed", "Due date changed", "bi-calendar-event", "updated"),
)
TYPE_MAP = {key: (label, icon, status) for key, label, icon, status in ACTIVITY_TYPES}


def financial_activity(profile, range_key, page_number=1, activity_type="", currency="USD"):
    """Return newest-first invoice activity, scoped to the owner and selected range."""
    window = date_window(range_key)
    bookings = ClientSession.objects.for_photographer(profile).exclude(status=ClientSession.Status.CANCELLED).order_by("-starts_at")
    actual_payment = InvoicePayment.objects.filter(invoice_id=OuterRef("pk"))
    invoices = (ClientInvoice.objects.for_photographer(profile).select_related("client").annotate(has_payment_record=Exists(actual_payment))
                .prefetch_related(Prefetch("client__sessions", queryset=bookings, to_attr="financial_bookings"))
                .order_by("-created_at"))
    if window.start:
        invoices = invoices.filter(created_at__date__gte=window.start)
    invoices = invoices.filter(created_at__date__lte=window.end)
    records = []
    def add_record(kind, invoice, amount, occurred_at):
        if activity_type and kind != activity_type:
            return
        label, icon, badge = TYPE_MAP[kind]
        booking = invoice.client.financial_bookings[0] if invoice.client.financial_bookings else None
        records.append({"type": kind, "label": label, "icon": icon, "status": badge,
                        "status_label": label, "client": str(invoice.client),
                        "client_url": reverse("photographer_workspace:client_detail", args=[invoice.client_id]),
                        "related": f"INV-{invoice.pk:06d}",
                        "record_url": f"{reverse('photographer_workspace:transactions')}?invoice={invoice.pk}",
                        "booking": booking.session_type if booking else "",
                        "booking_url": reverse("photographer_workspace:booking_detail", args=[booking.pk]) if booking else "",
                        "amount": format_currency(amount, currency), "occurred_at": occurred_at, "performed_by": "You"})

    for invoice in invoices:
        inferred_type = {
            ClientInvoice.Status.SENT: "invoice_sent",
            ClientInvoice.Status.PAID: "payment_received",
            ClientInvoice.Status.PARTIALLY_PAID: "payment_received",
            ClientInvoice.Status.VOID: "invoice_voided",
        }.get(invoice.status, "invoice_created")
        if invoice.has_payment_record and inferred_type == "payment_received":
            inferred_type = "invoice_sent"
        add_record(inferred_type, invoice, invoice.amount_paid if inferred_type == "payment_received" else invoice.total, invoice.created_at)

    payments = InvoicePayment.objects.for_photographer(profile).select_related("invoice__client").prefetch_related(
        Prefetch("invoice__client__sessions", queryset=bookings, to_attr="financial_bookings"))
    refunds = PaymentRefund.objects.for_photographer(profile).select_related("payment__invoice__client").prefetch_related(
        Prefetch("payment__invoice__client__sessions", queryset=bookings, to_attr="financial_bookings"))
    credits = InvoiceCredit.objects.for_photographer(profile).select_related("invoice__client").prefetch_related(
        Prefetch("invoice__client__sessions", queryset=bookings, to_attr="financial_bookings"))
    for queryset, field in ((payments, "paid_at"), (refunds, "refunded_at"), (credits, "applied_at")):
        if window.start:
            queryset = queryset.filter(**{f"{field}__date__gte": window.start})
        queryset = queryset.filter(**{f"{field}__date__lte": window.end})
        for item in queryset:
            if isinstance(item, InvoicePayment):
                kind = "payment_received" if item.status == InvoicePayment.Status.COMPLETED else "payment_failed" if item.status == InvoicePayment.Status.FAILED else None
                invoice = item.invoice
            elif isinstance(item, PaymentRefund):
                kind = "refund_completed" if item.status == PaymentRefund.Status.COMPLETED else "refund_initiated" if item.status == PaymentRefund.Status.PENDING else None
                invoice = item.payment.invoice
            else:
                kind = "credit_issued" if item.status == InvoiceCredit.Status.APPLIED else None
                invoice = item.invoice
            if kind:
                add_record(kind, invoice, item.amount, getattr(item, field))
    records.sort(key=lambda record: record["occurred_at"], reverse=True)
    paginator = Paginator(records, ACTIVITY_LIMIT)
    page = paginator.get_page(page_number)
    return {"records": page.object_list, "page": page, "types": ACTIVITY_TYPES,
            "selected_type": activity_type, "is_filtered": bool(activity_type), "limit": ACTIVITY_LIMIT}
