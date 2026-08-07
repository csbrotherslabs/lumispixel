"""Owner-scoped presentation data for the shared financial record drawer."""
from decimal import Decimal

from django.urls import reverse

from apps.clients.models import ClientActivity, ClientInvoice, ClientSession, InvoiceCredit, InvoicePayment, PaymentRefund
from apps.dashboard.financial import format_currency


RECORD_MODELS = {"invoice": ClientInvoice, "payment": InvoicePayment, "refund": PaymentRefund, "credit": InvoiceCredit}
PREFIXES = {"invoice": "INV", "payment": "PAY", "refund": "REF", "credit": "CRD"}


def financial_record_detail(profile, kind, pk, currency="USD"):
    """Fetch one record through its owner scope and return common drawer sections."""
    model = RECORD_MODELS.get(kind)
    if not model:
        return None
    related = "client" if kind == "invoice" else "payment__invoice__client" if kind == "refund" else "invoice__client"
    item = model.objects.for_photographer(profile).select_related(related).filter(pk=pk).first()
    if not item:
        return None
    invoice = item if kind == "invoice" else item.payment.invoice if kind == "refund" else item.invoice
    client = invoice.client
    booking = invoice.booking
    payments = list(invoice.payments.all())
    credits = list(invoice.credits.all())
    paid = sum((p.amount for p in payments if p.status == InvoicePayment.Status.COMPLETED), Decimal("0"))
    credited = sum((c.amount for c in credits if c.status == InvoiceCredit.Status.APPLIED), Decimal("0"))

    if kind == "invoice":
        amount, occurred = item.total, item.created_at
        summary = [("Subtotal", format_currency(item.total, currency)), ("Discount", format_currency(0, currency)),
                   ("Tax", format_currency(0, currency)), ("Total", format_currency(item.total, currency)),
                   ("Amount paid", format_currency(item.amount_paid, currency)), ("Credits applied", format_currency(credited, currency)),
                   ("Balance due", format_currency(item.balance, currency))]
        details = [("Issue date", item.created_at), ("Due date", item.due_date or "Not set"), ("Payment terms", "Due on receipt" if not item.due_date else "Due by stated date")]
        notes = item.internal_notes
    elif kind == "payment":
        amount, occurred = item.amount, item.paid_at
        summary = [("Gross amount", format_currency(item.amount, currency)), ("Processing fee", format_currency(item.processor_fee, currency)), ("Net amount", format_currency(item.amount - item.processor_fee, currency))]
        details = [("Payment date", item.paid_at), ("Payment method", item.get_method_display()), ("Source", "External" if item.method == InvoicePayment.Method.EXTERNAL else "Manual entry"),
                   ("External reference", item.external_reference or "Not recorded")]
        notes = item.internal_note
    elif kind == "refund":
        amount, occurred = item.amount, item.refunded_at
        summary = [("Refund amount", format_currency(item.amount, currency))]
        details = [("Original payment", f"PAY-{item.payment_id:06d}"), ("Refund reason", item.reason or "Not recorded"),
                   ("Refund date", item.refunded_at), ("Status", item.get_status_display())]
        notes = item.internal_note
    else:
        amount, occurred = item.amount, item.applied_at
        remaining = item.amount if item.status == InvoiceCredit.Status.DRAFT else Decimal("0")
        summary = [("Original amount", format_currency(item.amount, currency)), ("Remaining amount", format_currency(remaining, currency))]
        details = [("Reason", item.reason or "Not recorded"), ("Expiration date", item.expires_at or "No expiration"), ("Applied date", item.applied_at)]
        notes = item.internal_note

    related_records = [{"label": f"Payment PAY-{p.pk:06d}", "url": f"?payment={p.pk}"} for p in payments if kind != "payment" or p.pk != item.pk]
    related_records += [{"label": f"Credit CRD-{c.pk:06d}", "url": f"?credit={c.pk}"} for c in credits if kind != "credit" or c.pk != item.pk]
    related_records += [{"label": f"Refund REF-{r.pk:06d}", "url": f"?refund={r.pk}"} for p in payments for r in p.refunds.all() if kind != "refund" or r.pk != item.pk]
    activities = list(ClientActivity.objects.for_photographer(profile).filter(client=client).order_by("-occurred_at")[:8])
    timeline = [{"label": a.get_event_type_display(), "detail": a.description, "at": a.occurred_at} for a in activities]
    timeline.append({"label": "Created", "detail": f"{kind.title()} record created", "at": item.created_at})
    return {"kind": kind, "type_label": kind.title(), "reference": f"{PREFIXES[kind]}-{item.pk:06d}",
            "status": item.status, "status_label": item.get_status_display(), "amount": format_currency(amount, currency),
            "summary": summary, "details": details, "client": client, "client_url": reverse("photographer_workspace:client_detail", args=[client.pk]),
            "booking": booking, "booking_url": reverse("photographer_workspace:booking_detail", args=[booking.pk]) if booking else "",
            "invoice_reference": f"INV-{invoice.pk:06d}", "invoice_url": reverse("photographer_workspace:invoice_view", args=[invoice.pk]),
            "related_records": related_records, "timeline": sorted(timeline, key=lambda event: event["at"], reverse=True), "notes": notes,
            "occurred": occurred}
