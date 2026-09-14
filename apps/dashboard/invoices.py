"""Server-authoritative invoice creation and lifecycle operations."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.clients.models import Client, ClientInvoice, ClientSession, InvoiceActivity, InvoiceLineItem, InvoicePaymentSchedule

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class InvoiceDeliveryError(Exception):
    """The invoice email could not be accepted by the configured email backend."""


def money(value, field):
    try:
        return Decimal(value or "0").quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValidationError({field: "Enter a valid monetary amount."})


def next_invoice_number(profile):
    """Return the next display number, locking existing rows only inside an atomic save."""
    year = timezone.localdate().year
    prefix = f"INV-{year}-"
    invoices = ClientInvoice.objects.filter(photographer=profile, invoice_number__startswith=prefix)
    if transaction.get_connection().in_atomic_block:
        invoices = invoices.select_for_update()
    last = invoices.order_by("-invoice_number").values_list("invoice_number", flat=True).first()
    sequence = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
    return f"{prefix}{sequence:04d}"


def _rows(post, prefix, fields):
    columns = {field: post.getlist(f"{prefix}_{field}[]") for field in fields}
    length = max((len(values) for values in columns.values()), default=0)
    return [{field: columns[field][index] if index < len(columns[field]) else "" for field in fields}
            for index in range(length)]


def calculate_items(post):
    rows, errors = [], []
    for index, row in enumerate(_rows(post, "item", ("type", "description", "quantity", "unit_price", "discount", "tax"))):
        if not any(row.values()):
            continue
        try:
            quantity, unit = money(row["quantity"], "line_items"), money(row["unit_price"], "line_items")
            discount, tax = money(row["discount"], "line_items"), money(row["tax"], "line_items")
            if not row["description"].strip() or quantity <= 0 or unit < 0 or not ZERO <= discount <= 100 or not ZERO <= tax <= 100:
                raise ValueError
            gross = (quantity * unit).quantize(CENT)
            discount_amount = (gross * discount / 100).quantize(CENT)
            taxable = gross - discount_amount
            tax_amount = (taxable * tax / 100).quantize(CENT)
            rows.append({**row, "quantity": quantity, "unit_price": unit, "discount_percent": discount,
                         "tax_percent": tax, "subtotal": gross, "discount_amount": discount_amount,
                         "tax_amount": tax_amount, "total": taxable + tax_amount})
        except (ValidationError, ValueError):
            errors.append(f"Line item {index + 1} has invalid values.")
    if not rows:
        errors.append("Add at least one valid line item.")
    if errors:
        raise ValidationError({"line_items": errors})
    return rows


def _invoice_recipient(invoice):
    recipient = (invoice.client.email or "").strip()
    if not recipient:
        raise ValidationError({"client": "An email address is required to send this invoice."})
    try:
        validate_email(recipient)
    except ValidationError as exc:
        raise ValidationError({"client": "Enter a valid client email address before sending this invoice."}) from exc
    return recipient


def _studio_name(invoice):
    profile = invoice.photographer
    user = profile.user
    return profile.business_name or profile.display_name or user.full_name or user.email


def deliver_invoice_email(invoice):
    """Deliver one invoice email without mutating invoice lifecycle state."""
    recipient = _invoice_recipient(invoice)
    studio_name = _studio_name(invoice)
    context = {"invoice": invoice, "studio_name": studio_name}
    invoice_html = render_to_string("photographer_workspace/invoices/print.html", context)
    message = EmailMultiAlternatives(
        f"Invoice {invoice.invoice_number} from {studio_name}",
        render_to_string("photographer_workspace/invoices/email/invoice.txt", context),
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
    )
    message.attach_alternative(
        render_to_string("photographer_workspace/invoices/email/invoice.html", context),
        "text/html",
    )
    message.attach(f"{invoice.invoice_number}.html", invoice_html, "text/html")
    try:
        delivered = message.send(fail_silently=False)
    except Exception as exc:
        raise InvoiceDeliveryError("Invoice email delivery failed.") from exc
    if delivered != 1:
        raise InvoiceDeliveryError("Invoice email delivery failed.")


def _mark_invoice_delivered(invoice, action):
    if invoice.status == ClientInvoice.Status.DRAFT:
        invoice.status = ClientInvoice.Status.SENT
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=["status", "sent_at"])
    InvoiceActivity.objects.create(
        photographer=invoice.photographer,
        invoice=invoice,
        action=action,
        description="Invoice emailed to client.",
    )


@transaction.atomic
def send_existing_invoice(profile, invoice, action="send"):
    """Deliver an existing invoice, then record state only after successful delivery."""
    invoice = ClientInvoice.objects.select_for_update().select_related(
        "client", "photographer", "photographer__user"
    ).prefetch_related("line_items", "payment_schedule").get(pk=invoice.pk, photographer=profile)
    if action not in {"send", "resend"}:
        raise ValidationError("Choose a valid invoice delivery action.")
    if invoice.status not in {
        ClientInvoice.Status.DRAFT, ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID
    }:
        raise ValidationError("This invoice cannot be sent in its current state.")
    _invoice_recipient(invoice)
    deliver_invoice_email(invoice)
    _mark_invoice_delivered(invoice, action)
    return invoice


@transaction.atomic
def save_invoice(profile, post, invoice=None, send=False):
    if invoice and invoice.is_locked:
        raise ValidationError("Paid and void invoices cannot be edited.")
    client_id = post.get("client")
    if client_id:
        client = Client.objects.for_photographer(profile).filter(pk=client_id).first()
    else:
        first_name = post.get("new_client_first_name", "").strip()
        email = post.get("new_client_email", "").strip()
        client = Client.objects.create(photographer=profile, first_name=first_name, email=email) if first_name and email else None
    if not client:
        raise ValidationError({"client": "Select a client or provide a new client's name and email."})
    booking = None
    if post.get("booking"):
        booking = ClientSession.objects.for_photographer(profile).filter(pk=post["booking"], client=client).first()
        if not booking:
            raise ValidationError({"booking": "Select a booking belonging to this client."})
    items = calculate_items(post)
    subtotal = sum((row["subtotal"] for row in items), ZERO)
    discounts = sum((row["discount_amount"] for row in items), ZERO)
    taxes = sum((row["tax_amount"] for row in items), ZERO)
    total = subtotal - discounts + taxes
    try:
        issue_date = timezone.datetime.strptime(post.get("issue_date", ""), "%Y-%m-%d").date()
        terms = int(post.get("payment_terms") or 30)
        due_date = timezone.datetime.strptime(post["due_date"], "%Y-%m-%d").date() if post.get("due_date") else issue_date + timedelta(days=terms)
        if due_date < issue_date or terms < 0:
            raise ValueError
    except (ValueError, TypeError):
        raise ValidationError({"due_date": "Due date must be on or after the issue date."})
    invoice = invoice or ClientInvoice(photographer=profile, invoice_number=next_invoice_number(profile))
    invoice.client, invoice.booking = client, booking
    invoice.issue_date, invoice.due_date, invoice.payment_terms = issue_date, due_date, terms
    invoice.currency = post.get("currency", "USD") if post.get("currency") in {"USD", "CAD", "EUR", "GBP", "AUD"} else "USD"
    invoice.subtotal, invoice.discount_total, invoice.tax_total, invoice.total = subtotal, discounts, taxes, total
    invoice.client_notes, invoice.internal_notes, invoice.terms = post.get("client_notes", ""), post.get("internal_notes", ""), post.get("terms", "")
    invoice.delivery_email, invoice.reminders_enabled = post.get("delivery_email") == "on", post.get("reminders_enabled") == "on"
    if send:
        _invoice_recipient(invoice)
    invoice.full_clean()
    invoice.save()
    invoice.line_items.all().delete()
    InvoiceLineItem.objects.bulk_create([InvoiceLineItem(invoice=invoice, item_type=row["type"] if row["type"] in InvoiceLineItem.ItemType.values else "custom",
        description=row["description"].strip(), quantity=row["quantity"], unit_price=row["unit_price"], discount_percent=row["discount_percent"],
        tax_percent=row["tax_percent"], subtotal=row["subtotal"], total=row["total"], position=i) for i, row in enumerate(items)])
    invoice.payment_schedule.all().delete()
    schedules = _rows(post, "schedule", ("label", "amount", "due_date"))
    for i, row in enumerate(schedules):
        if not any(row.values()): continue
        amount = money(row["amount"], "payment_schedule")
        try: scheduled_date = timezone.datetime.strptime(row["due_date"], "%Y-%m-%d").date()
        except ValueError: raise ValidationError({"payment_schedule": "Every payment needs a valid due date."})
        InvoicePaymentSchedule.objects.create(invoice=invoice, label=row["label"] or f"Payment {i + 1}", amount=amount, due_date=scheduled_date, position=i)
    if invoice.payment_schedule.exists() and sum((p.amount for p in invoice.payment_schedule.all()), ZERO) != total:
        raise ValidationError({"payment_schedule": "Scheduled payments must add up to the invoice total."})
    if send:
        deliver_invoice_email(invoice)
        _mark_invoice_delivered(invoice, "sent")
    else:
        InvoiceActivity.objects.create(
            photographer=profile, invoice=invoice, action="saved", description="Invoice saved as draft."
        )
    return invoice
