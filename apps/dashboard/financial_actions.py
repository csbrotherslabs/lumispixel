"""Atomic, owner-scoped mutations for manual financial activity."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.clients.models import Client, ClientInvoice, InvoiceActivity, InvoiceCredit, InvoicePayment, PaymentRefund

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value, field="amount"):
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "Enter a valid monetary amount."})
    if result <= ZERO:
        raise ValidationError({field: "Amount must be greater than zero."})
    return result


def _invoice_status(invoice):
    if invoice.amount_paid <= ZERO:
        return ClientInvoice.Status.SENT
    return ClientInvoice.Status.PAID if invoice.amount_paid == invoice.total else ClientInvoice.Status.PARTIALLY_PAID


def _duplicate(model, profile, key):
    return model.objects.for_photographer(profile).filter(submission_key=key).first() if key else None


@transaction.atomic
def record_payment(profile, data):
    """Record a complete payment and update its invoice under row locks."""
    key = str(data.get("submission_key", "")).strip()
    duplicate = _duplicate(InvoicePayment, profile, key)
    if duplicate:
        return duplicate, True
    client = Client.objects.for_photographer(profile).filter(pk=data.get("client")).first()
    if not client:
        raise ValidationError({"client": "Select a client in this workspace."})
    invoice = ClientInvoice.objects.select_for_update().for_photographer(profile).filter(pk=data.get("invoice"), client=client).first()
    if not invoice:
        raise ValidationError({"invoice": "Select an invoice belonging to this client."})
    if invoice.status in {ClientInvoice.Status.DRAFT, ClientInvoice.Status.VOID}:
        raise ValidationError({"invoice": "Payments cannot be recorded against this invoice."})
    amount, fee = money(data.get("amount")), money(data.get("processor_fee"), "processor_fee") if data.get("processor_fee") else ZERO
    if amount > invoice.balance:
        raise ValidationError({"amount": "Payment cannot exceed the invoice balance."})
    method = data.get("method")
    if method not in dict(InvoicePayment.Method.choices):
        raise ValidationError({"method": "Select a supported payment method."})
    paid_at = data.get("paid_at") or timezone.now()
    payment = InvoicePayment.objects.create(
        photographer=profile, invoice=invoice, amount=amount, method=method, paid_at=paid_at,
        external_reference=str(data.get("external_reference", "")).strip(), processor_fee=fee,
        internal_note=str(data.get("internal_note", "")).strip(), submission_key=key,
    )
    invoice.amount_paid += amount
    invoice.status = _invoice_status(invoice)
    invoice.save(update_fields=["amount_paid", "status"])
    InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="payment_received",
                                   description=f"Payment PAY-{payment.pk:06d} of {amount} recorded.")
    return payment, False


@transaction.atomic
def issue_refund(profile, data):
    """Refund no more than the locked payment's unrefunded completed value."""
    key = str(data.get("submission_key", "")).strip()
    duplicate = _duplicate(PaymentRefund, profile, key)
    if duplicate:
        return duplicate, True
    payment = (InvoicePayment.objects.select_for_update().for_photographer(profile)
               .select_related("invoice").filter(pk=data.get("payment"), status=InvoicePayment.Status.COMPLETED).first())
    if not payment:
        raise ValidationError({"payment": "Select an eligible completed payment."})
    reason = str(data.get("reason", "")).strip()
    if not reason:
        raise ValidationError({"reason": "A refund reason is required."})
    amount = money(data.get("amount"))
    refunded = payment.refunds.filter(status=PaymentRefund.Status.COMPLETED).aggregate(total=Sum("amount"))["total"] or ZERO
    if amount > payment.amount - refunded:
        raise ValidationError({"amount": "Refund cannot exceed the remaining refundable amount."})
    refund = PaymentRefund.objects.create(photographer=profile, payment=payment, amount=amount, reason=reason,
        internal_note=str(data.get("internal_note", "")).strip(), submission_key=key)
    invoice = ClientInvoice.objects.select_for_update().get(pk=payment.invoice_id)
    invoice.amount_paid = max(ZERO, invoice.amount_paid - amount)
    invoice.status = _invoice_status(invoice)
    invoice.save(update_fields=["amount_paid", "status"])
    # Keep the original cash receipt completed: reporting subtracts this refund
    # once, rather than dropping the receipt and then subtracting it again.
    InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="refund_completed",
                                   description=f"Refund REF-{refund.pk:06d} of {amount} completed: {reason}")
    return refund, False


@transaction.atomic
def add_credit(profile, data):
    """Issue client credit, retaining original and spendable values."""
    key = str(data.get("submission_key", "")).strip()
    duplicate = _duplicate(InvoiceCredit, profile, key)
    if duplicate:
        return duplicate, True
    client = Client.objects.for_photographer(profile).filter(pk=data.get("client")).first()
    if not client:
        raise ValidationError({"client": "Select a client in this workspace."})
    invoice = ClientInvoice.objects.select_for_update().for_photographer(profile).filter(pk=data.get("invoice"), client=client).first()
    if not invoice:
        raise ValidationError({"invoice": "Select an invoice belonging to this client."})
    reason = str(data.get("reason", "")).strip()
    if not reason:
        raise ValidationError({"reason": "A credit reason is required."})
    amount = money(data.get("amount"))
    credit = InvoiceCredit.objects.create(photographer=profile, invoice=invoice, amount=amount,
        original_amount=amount, remaining_amount=amount, status=InvoiceCredit.Status.DRAFT, reason=reason,
        expires_at=data.get("expires_at") or None, internal_note=str(data.get("internal_note", "")).strip(), submission_key=key)
    InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="credit_issued",
                                   description=f"Credit CRD-{credit.pk:06d} of {amount} issued: {reason}")
    return credit, False


@transaction.atomic
def use_credit(profile, credit_id, amount):
    """Atomically consume part of a credit without allowing a negative remainder."""
    credit = InvoiceCredit.objects.select_for_update().for_photographer(profile).filter(pk=credit_id).first()
    if not credit:
        raise ValidationError({"credit": "Credit was not found."})
    value = money(amount)
    if value > credit.remaining_amount:
        raise ValidationError({"amount": "Credit use cannot exceed the remaining value."})
    credit.remaining_amount -= value
    credit.status = InvoiceCredit.Status.APPLIED if credit.remaining_amount == ZERO else InvoiceCredit.Status.DRAFT
    credit.save(update_fields=["remaining_amount", "status"])
    return credit
