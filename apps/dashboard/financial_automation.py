"""Financial communications backed by the transactional outbox."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from django.utils.html import format_html

from apps.clients.models import ClientInvoice, ClientSession, InvoicePayment
from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


def queue_receipt(payment):
    invoice = payment.invoice
    if not invoice.client.email:
        return None
    return queue_transactional_email(
        event_key=f"payment.receipt:{payment.pk}",
        subject=f"Payment receipt for {invoice.invoice_number}",
        plain_body=f"Payment received: {invoice.currency} {payment.amount:.2f}. Invoice: {invoice.invoice_number}. Receipt reference: PAY-{payment.pk:06d}.",
        html_body=str(format_html("<h1>Payment received</h1><p>Invoice: {}</p><p>Amount: {} {}</p><p>Receipt: PAY-{}</p><p>Thank you for your payment.</p>", invoice.invoice_number, invoice.currency, format(payment.amount, ".2f"), str(payment.pk).zfill(6))),
        recipients=[invoice.client.email],
        lifecycle_kind="payment.receipt",
        lifecycle_context={"payment_id": payment.pk, "studio_id": payment.photographer_id},
    )


def outstanding_booking(booking):
    paid = booking.invoices.filter(
        photographer_id=booking.photographer_id, client_id=booking.client_id,
        currency=booking.payment_currency,
        status__in=["sent", "partially_paid", "paid"],
    ).aggregate(value=Sum("amount_paid"))["value"] or Decimal("0")
    return max(Decimal("0"), booking.booking_value - paid)


def reminder_eligible(booking, day):
    return (
        booking.event_kind == ClientSession.EventKind.BOOKING
        and booking.status in [ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED]
        and booking.pricing_confirmed and booking.booking_value > 0
        and booking.client.photographer_id == booking.photographer_id
        and booking.photographer.user.can_login
        and timezone.localdate(booking.starts_at) in [day - timedelta(days=1), day + timedelta(days=1)]
        and outstanding_booking(booking) > 0
    )


@transaction.atomic
def queue_booking_reminder(booking_id, day):
    booking = ClientSession.objects.select_for_update(of=("self",)).select_related(
        "photographer__user", "client").get(pk=booking_id)
    if not reminder_eligible(booking, day):
        return False
    key = f"booking.balance:{booking.pk}:{day.isoformat()}"
    if EmailDelivery.objects.filter(event_key=key).exists():
        return False
    return bool(queue_transactional_email(
        event_key=key, subject="Booking payment reminder",
        plain_body=f"Booking #{booking.pk} ({timezone.localdate(booking.starts_at)}): outstanding agreed balance {booking.payment_currency} {outstanding_booking(booking):.2f}. Please review your booking payments.",
        html_body=str(format_html("<h1>Outstanding booking payment</h1><p>Booking #{} · {}</p><p>Outstanding balance: {} {}</p><p>Please review your booking payments.</p>", booking.pk, timezone.localdate(booking.starts_at), booking.payment_currency, format(outstanding_booking(booking), ".2f"))),
        recipients=[booking.photographer.user.email], lifecycle_kind="booking.balance",
        lifecycle_context={"booking_id": booking.pk, "studio_id": booking.photographer_id,
                           "day": day.isoformat(), "starts_at": booking.starts_at.isoformat(),
                           "balance": str(outstanding_booking(booking)), "currency": booking.payment_currency},
    ))


def scan_booking_reminders():
    day = timezone.localdate()
    ids = ClientSession.objects.filter(
        starts_at__date__in=[day - timedelta(days=1), day + timedelta(days=1)],
        pricing_confirmed=True, booking_value__gt=0, event_kind="booking",
        status__in=["confirmed", "completed"],
    ).values_list("pk", flat=True)
    return sum(queue_booking_reminder(pk, day) for pk in ids.iterator())


def financial_metrics():
    invoices = ClientInvoice.objects.filter(status__in=["sent", "partially_paid", "paid"])
    open_invoices = invoices.filter(total__gt=F("amount_paid"))
    today = timezone.localdate()
    emails = EmailDelivery.objects.filter(lifecycle_kind__in=["invoice.email", "payment.receipt", "booking.balance"])
    return {
        "upcoming_payments": open_invoices.filter(due_date__gte=today).count(),
        "invoices_issued": invoices.count(),
        "invoices_sent": emails.filter(lifecycle_kind="invoice.email", lifecycle_context__purpose="issue", status="sent").count(),
        "payments_processed": InvoicePayment.objects.filter(status="completed").count(),
        "receipts_sent": emails.filter(lifecycle_kind="payment.receipt", status="sent").count(),
        "late_payments": open_invoices.filter(due_date__lt=today).count(),
        "failed_financial_emails": emails.filter(status__in=["dead", "failed", "uncertain"]).count(),
    }
