"""Safe, studio-scoped bulk operations and CSV exports for financial records."""
import csv
import io
import zipfile

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.clients.models import ClientInvoice, InvoiceActivity, InvoiceCredit, InvoicePayment, PaymentRefund

EXPORT_COLUMNS = {
    "record_type": ("Record type", "type_label"), "reference": ("Reference", "reference"),
    "client": ("Client", "client"), "client_email": ("Client email", "client_email"),
    "booking": ("Booking", "booking"), "date": ("Date", "date"), "due_date": ("Due date", "due_date"),
    "gross_amount": ("Gross amount", "gross_amount"), "fees": ("Fees", "fee_amount"),
    "net_amount": ("Net amount", "net_amount"), "balance": ("Balance", "balance_amount"),
    "currency": ("Currency", "currency"), "status": ("Status", "status_label"),
    "payment_method": ("Payment method", "method"), "source": ("Source", "source"),
}
DEFAULT_EXPORT_COLUMNS = tuple(EXPORT_COLUMNS)


def parse_record_ids(values):
    """Parse canonical type-id tokens, rejecting malformed and duplicate input."""
    parsed = []
    for value in values:
        try:
            kind, raw_pk = value.split("-", 1)
            pk = int(raw_pk)
        except (AttributeError, TypeError, ValueError):
            raise ValidationError("The selected financial records are invalid.")
        if kind not in {"invoice", "payment", "refund", "credit"} or pk < 1 or (kind, pk) in parsed:
            raise ValidationError("The selected financial records are invalid.")
        parsed.append((kind, pk))
    if not parsed:
        raise ValidationError("Select at least one financial record.")
    return parsed


def selected_objects(profile, values):
    parsed = parse_record_ids(values)
    models = {"invoice": ClientInvoice, "payment": InvoicePayment, "refund": PaymentRefund, "credit": InvoiceCredit}
    grouped = {kind: [] for kind in models}
    for kind, pk in parsed:
        grouped[kind].append(pk)
    found = {}
    for kind, pks in grouped.items():
        if not pks:
            continue
        queryset = models[kind].objects.for_photographer(profile).filter(pk__in=pks)
        if kind == "invoice":
            queryset = queryset.select_related("client").prefetch_related("line_items")
        elif kind == "refund":
            queryset = queryset.select_related("payment__invoice__client")
        else:
            queryset = queryset.select_related("invoice__client")
        found.update({(kind, record.pk): record for record in queryset})
    if len(found) != len(parsed):
        # Do not reveal whether a missing id belongs to another studio.
        raise ValidationError("One or more selected records are unavailable.")
    return [(kind, found[(kind, pk)]) for kind, pk in parsed]


def available_actions(rows):
    """Return only actions which are safe for every selected row."""
    if not rows:
        return []
    actions = ["export", "note"]
    invoices = [row for row in rows if row[0] == "invoice"]
    if len(invoices) == len(rows):
        objects = [row[1] for row in invoices]
        if all(obj.status in {ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID}
               and obj.reminders_enabled and obj.client.email for obj in objects):
            actions.append("remind")
        if all(obj.status == ClientInvoice.Status.DRAFT and not obj.delivery_email for obj in objects):
            actions.append("mark_sent")
        if all(obj.status != ClientInvoice.Status.VOID for obj in objects):
            actions.append("download")
        if all(obj.status == ClientInvoice.Status.DRAFT for obj in objects):
            actions.append("void")
    return actions


@transaction.atomic
def run_bulk_action(profile, values, action, note=""):
    rows = selected_objects(profile, values)
    if action not in available_actions(rows) or action in {"export", "download"}:
        raise ValidationError("That action is not safe for the selected record types and statuses.")
    now = timezone.now()
    for kind, record in rows:
        invoice = record if kind == "invoice" else record.payment.invoice if kind == "refund" else record.invoice
        if action == "note":
            text = note.strip()
            if not text:
                raise ValidationError("Enter an internal note.")
            field = "internal_notes" if kind == "invoice" else "internal_note"
            current = getattr(record, field, "")
            setattr(record, field, f"{current}\n{text}".strip())
            record.save(update_fields=[field])
        elif action == "remind":
            InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="reminder",
                                           description="Invoice reminder queued for delivery.")
        elif action == "mark_sent":
            invoice.status, invoice.sent_at = ClientInvoice.Status.SENT, now
            invoice.save(update_fields=["status", "sent_at"])
            InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="sent",
                                           description="External invoice marked as sent.")
        elif action == "void":
            invoice.status = ClientInvoice.Status.VOID
            invoice.save(update_fields=["status"])
            InvoiceActivity.objects.create(photographer=profile, invoice=invoice, action="void",
                                           description="Draft invoice voided in bulk.")
    return len(rows)


def csv_bytes(rows, requested_columns=None):
    columns = [key for key in (requested_columns or DEFAULT_EXPORT_COLUMNS) if key in EXPORT_COLUMNS]
    if not columns:
        raise ValidationError("Select at least one approved export column.")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow([EXPORT_COLUMNS[key][0] for key in columns])
    for row in rows:
        values = []
        for key in columns:
            value = row.get(EXPORT_COLUMNS[key][1], "")
            values.append(value.isoformat() if hasattr(value, "isoformat") else value)
        writer.writerow(values)
    return "\ufeff".encode() + stream.getvalue().encode("utf-8")


def invoice_zip(profile, values, render_invoice):
    records = selected_objects(profile, values)
    if "download" not in available_actions(records):
        raise ValidationError("Only eligible invoices can be downloaded together.")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for _, invoice in records:
            archive.writestr(f"{invoice.invoice_number or f'INV-{invoice.pk:06d}'}.html", render_invoice(invoice))
    return output.getvalue()
