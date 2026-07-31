"""Owner-scoped, display-ready activity for the financial overview."""
from django.core.paginator import Paginator
from django.urls import reverse

from apps.clients.models import ClientInvoice
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
    invoices = ClientInvoice.objects.for_photographer(profile).select_related("client").order_by("-created_at")
    if window.start:
        invoices = invoices.filter(created_at__date__gte=window.start)
    invoices = invoices.filter(created_at__date__lte=window.end)
    records = []
    for invoice in invoices:
        inferred_type = {
            ClientInvoice.Status.SENT: "invoice_sent",
            ClientInvoice.Status.PAID: "payment_received",
            ClientInvoice.Status.PARTIALLY_PAID: "payment_received",
            ClientInvoice.Status.VOID: "invoice_voided",
        }.get(invoice.status, "invoice_created")
        if activity_type and inferred_type != activity_type:
            continue
        label, icon, badge = TYPE_MAP[inferred_type]
        booking = invoice.client.sessions.exclude(status="cancelled").order_by("-starts_at").first()
        records.append({
            "type": inferred_type, "label": label, "icon": icon, "status": badge,
            "status_label": dict(ClientInvoice.Status.choices).get(invoice.status, badge.title()),
            "client": str(invoice.client), "client_url": reverse("photographer_workspace:client_detail", args=[invoice.client_id]),
            "related": f"INV-{invoice.pk:06d}",
            "record_url": f"{reverse('photographer_workspace:transactions')}?invoice={invoice.pk}",
            "booking": booking.session_type if booking else "", 
            "booking_url": reverse("photographer_workspace:booking_detail", args=[booking.pk]) if booking else "",
            "amount": format_currency(invoice.amount_paid if inferred_type == "payment_received" else invoice.total, currency),
            "occurred_at": invoice.created_at, "performed_by": "You",
        })
    paginator = Paginator(records, ACTIVITY_LIMIT)
    page = paginator.get_page(page_number)
    return {"records": page.object_list, "page": page, "types": ACTIVITY_TYPES,
            "selected_type": activity_type, "is_filtered": bool(activity_type), "limit": ACTIVITY_LIMIT}
