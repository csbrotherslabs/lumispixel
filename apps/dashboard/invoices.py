"""Server-authoritative invoice creation and lifecycle operations."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.clients.models import Client, ClientInvoice, ClientSession, InvoiceActivity, InvoiceLineItem, InvoicePaymentSchedule

from apps.clients.payment_terms import SUPPORTED_CURRENCIES

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class InvoiceDeliveryError(ValidationError):
    """An invoice email could not be delivered to the client."""


def money(value, field):
    try:
        amount = Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
        if not amount.is_finite():
            raise InvalidOperation
        return amount
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "Enter a valid monetary amount."})


def next_invoice_number(profile):
    """Return the next display number, locking existing rows only inside an atomic save."""
    year = timezone.localdate().year
    prefix = f"INV-{year}-"
    invoices = ClientInvoice.objects.filter(photographer=profile, invoice_number__startswith=prefix)
    if transaction.get_connection().in_atomic_block:
        # Lock a stable parent even when no invoices exist yet.
        type(profile).objects.select_for_update().get(pk=profile.pk)
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


def queue_invoice_email(invoice, profile, *, purpose="issue"):
    """Persist a single intentional send per invoice/purpose/day (issue is once)."""
    from apps.notifications.email_delivery import queue_transactional_email
    from apps.notifications.models import EmailDelivery
    if invoice.photographer_id != profile.pk or not invoice.client.email:
        raise ValidationError("Invoice recipient is unavailable.")
    if purpose not in {"issue", "resend", "reminder"}:
        raise ValidationError("Invalid email purpose.")
    prefix = f"invoice:{profile.pk}:{invoice.pk}:"
    key = prefix + purpose
    if purpose != "issue":
        key += ":" + timezone.localdate().isoformat()
    # Caller holds invoice lock (or has just created the invoice).
    if EmailDelivery.objects.filter(event_key__startswith=prefix, status__in=[
        "pending", "retry", "sending", "uncertain"
    ]).exclude(event_key=key).exists():
        raise ValidationError("An earlier invoice email is still pending or uncertain.")
    existing = EmailDelivery.objects.filter(event_key=key).first()
    if existing:
        return existing
    studio_name = profile.business_name or profile.display_name or profile.user.full_name or profile.user.email
    context = {"invoice": invoice, "studio_name": studio_name}
    subject = f"Invoice {invoice.invoice_number} from {studio_name}"
    if purpose == "reminder":
        subject = "Payment reminder: " + subject
    try:
        delivery = queue_transactional_email(event_key=key, subject=subject,
            plain_body=render_to_string("clients/invoices/email/invoice.txt", context),
            html_body=render_to_string("clients/invoices/email/invoice.html", context),
            recipients=[invoice.client.email], lifecycle_kind="invoice.email",
            lifecycle_context={"invoice_id": invoice.pk, "studio_id": profile.pk, "purpose": purpose,
                "amount_paid": str(invoice.amount_paid), "total": str(invoice.total),
                "currency": invoice.currency, "due_date": invoice.due_date.isoformat() if invoice.due_date else None})
    except (ValueError, ValidationError) as exc:
        raise InvoiceDeliveryError("Invoice email could not be queued.") from exc
    if delivery is None:
        raise InvoiceDeliveryError("Invoice email could not be queued.")
    return delivery


@transaction.atomic
def save_invoice(profile, post, invoice=None, send=False):
    type(profile).objects.select_for_update().get(pk=profile.pk)
    if invoice:
        invoice = ClientInvoice.objects.select_for_update().get(pk=invoice.pk, photographer=profile)
    if invoice and invoice.status != ClientInvoice.Status.DRAFT:
        raise ValidationError("Only draft invoices can be edited.")
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
        booking = ClientSession.objects.select_for_update().for_photographer(profile).filter(pk=post["booking"], client=client).first()
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
    currency = post.get("currency") or "USD"
    if currency not in SUPPORTED_CURRENCIES:
        raise ValidationError({"currency": "Select a supported currency."})
    if booking:
        if not booking.pricing_confirmed or booking.payment_currency != currency:
            raise ValidationError({"booking": "Confirm booking pricing and use its agreed currency."})
        from django.db.models import Sum
        billed = ClientInvoice.objects.filter(booking=booking, photographer=profile).exclude(status=ClientInvoice.Status.VOID).exclude(pk=invoice.pk).aggregate(value=Sum("total"))["value"] or ZERO
        if billed + total > booking.booking_value:
            raise ValidationError({"booking": "Combined invoices cannot exceed the agreed booking value."})
    invoice.currency = currency
    invoice.subtotal, invoice.discount_total, invoice.tax_total, invoice.total = subtotal, discounts, taxes, total
    invoice.client_notes, invoice.internal_notes, invoice.terms = post.get("client_notes", ""), post.get("internal_notes", ""), post.get("terms", "")
    invoice.delivery_email, invoice.reminders_enabled = post.get("delivery_email") == "on", post.get("reminders_enabled") == "on"
    if send and not client.email:
        raise ValidationError({"client": "An email address is required to send this invoice."})
    invoice.full_clean()
    invoice.save()
    invoice.line_items.all().delete()
    InvoiceLineItem.objects.bulk_create([InvoiceLineItem(invoice=invoice, item_type=row["type"] if row["type"] in InvoiceLineItem.ItemType.values else "custom",
        description=row["description"].strip(), quantity=row["quantity"], unit_price=row["unit_price"], discount_percent=row["discount_percent"],
        tax_percent=row["tax_percent"], subtotal=row["subtotal"], total=row["total"], position=i) for i, row in enumerate(items)])
    invoice.payment_schedule.all().delete()
    schedules = _rows(post, "schedule", ("label", "amount", "due_date"))
    for i, row in enumerate(schedules):
        if not any(row.values()):
            continue
        amount = money(row["amount"], "payment_schedule")
        try:
            scheduled_date = timezone.datetime.strptime(row["due_date"], "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"payment_schedule": "Every payment needs a valid due date."})
        if amount <= ZERO or scheduled_date < issue_date:
            raise ValidationError({"payment_schedule": "Payments must be positive and due on or after issuance."})
        InvoicePaymentSchedule.objects.create(invoice=invoice, label=row["label"] or f"Payment {i + 1}", amount=amount, due_date=scheduled_date, position=i)
    if invoice.payment_schedule.exists() and sum((p.amount for p in invoice.payment_schedule.all()), ZERO) != total:
        raise ValidationError({"payment_schedule": "Scheduled payments must add up to the invoice total."})
    if send:
        queue_invoice_email(invoice, profile)
        invoice.status, invoice.sent_at = ClientInvoice.Status.SENT, timezone.now()
        invoice.save(update_fields=["status", "sent_at"])
    InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="email_queued" if send else "saved",
                                   description="Invoice issued; email queued for delivery." if send else "Invoice saved as draft.")
    return invoice
