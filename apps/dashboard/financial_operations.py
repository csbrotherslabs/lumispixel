"""Display-ready records for the Financial Overview operational panels."""
from django.db.models import DecimalField, ExpressionWrapper, F
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import ClientInvoice, ClientSession
from apps.dashboard.financial import format_currency

MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)
PANEL_LIMIT = 5


def _initials(client):
    return "".join(part[0].upper() for part in (client.first_name, client.last_name) if part)[:2] or "CL"


def _booking_for(client, sessions_by_client):
    sessions = sessions_by_client.get(client.pk, [])
    return sessions[0] if sessions else None


def financial_operations(profile, currency="USD", today=None):
    """Return capped, owner-scoped upcoming payments and urgent financial issues."""
    today = today or timezone.localdate()
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY_FIELD)
    invoices = (ClientInvoice.objects.for_photographer(profile).select_related("client")
                .exclude(status__in=(ClientInvoice.Status.PAID, ClientInvoice.Status.VOID))
                .annotate(balance_due=balance))
    sessions = (ClientSession.objects.for_photographer(profile).select_related("client")
                .exclude(status=ClientSession.Status.CANCELLED).order_by("-starts_at"))
    sessions_by_client = {}
    for session in sessions:
        sessions_by_client.setdefault(session.client_id, []).append(session)

    upcoming = []
    for invoice in invoices.filter(due_date__gte=today).order_by("due_date", "created_at")[:PANEL_LIMIT]:
        booking = _booking_for(invoice.client, sessions_by_client)
        days = (invoice.due_date - today).days
        upcoming.append({
            "client": str(invoice.client), "initials": _initials(invoice.client),
            "avatar": invoice.client.profile_photo.url if invoice.client.profile_photo else "",
            "booking": booking.session_type if booking else "General services",
            "invoice": f"INV-{invoice.pk:06d}", "due_date": invoice.due_date,
            "amount": format_currency(invoice.balance_due, currency),
            "status": invoice.get_status_display(), "status_key": invoice.status,
            "timing": "Due today" if days == 0 else f"Due in {days} day{'s' if days != 1 else ''}",
            "invoice_url": f"{reverse('photographer_workspace:transactions')}?invoice={invoice.pk}",
            "booking_url": reverse("photographer_workspace:booking_detail", args=[booking.pk]) if booking else reverse("photographer_workspace:bookings"),
            "client_url": reverse("photographer_workspace:client_detail", args=[invoice.client_id]),
        })

    attention, flagged_invoice_ids = [], set()
    def add_issue(invoice, issue, severity, action, age):
        flagged_invoice_ids.add(invoice.pk)
        attention.append({"issue": issue, "subject": str(invoice.client),
                          "detail": f"INV-{invoice.pk:06d}", "amount": format_currency(invoice.balance_due, currency),
                          "age": age, "severity": severity, "severity_label": severity.title(),
                          "action": action, "url": f"{reverse('photographer_workspace:transactions')}?invoice={invoice.pk}"})

    for invoice in invoices.filter(due_date__lt=today).order_by("due_date"):
        days = (today - invoice.due_date).days
        add_issue(invoice, "Overdue invoice", "critical" if days >= 30 else "high", "Send payment reminder", f"{days} day{'s' if days != 1 else ''} overdue")
    for invoice in invoices.filter(due_date=None).order_by("created_at"):
        add_issue(invoice, "Missing due date", "medium", "Add a due date", "Due date not set")

    invoiced_clients = set(ClientInvoice.objects.for_photographer(profile).values_list("client_id", flat=True))
    for session in sessions:
        if len(attention) >= PANEL_LIMIT:
            break
        unpaid = invoices.filter(client_id=session.client_id).exclude(pk__in=flagged_invoice_ids).order_by("due_date").first()
        if session.status == ClientSession.Status.COMPLETED and unpaid:
            add_issue(unpaid, "Completed booking with unpaid balance", "high", "Collect outstanding balance",
                      session.starts_at.date())
            continue
        if session.status == ClientSession.Status.CONFIRMED and session.client_id not in invoiced_clients:
            attention.append({"issue": "Booking without invoice", "subject": session.session_type,
                              "detail": str(session.client), "amount": "—", "age": session.starts_at.date(),
                              "severity": "medium", "severity_label": "Medium", "action": "Create invoice",
                              "url": f"{reverse('photographer_workspace:invoices')}?booking={session.pk}"})
    return {"upcoming": upcoming, "attention": attention[:PANEL_LIMIT], "limit": PANEL_LIMIT}
