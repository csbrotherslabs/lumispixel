from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clients.contracts import send_contract_for_review
from apps.clients.models import ClientInvoice, ClientTask, Contract, InvoiceActivity, InvoiceLineItem
from apps.dashboard.invoices import next_invoice_number
from apps.galleries.activity import log_gallery_activity
from apps.galleries.models import AccessToken, Gallery, GalleryActivity, GalleryInvitation
from apps.galleries.services import GalleryInvitationDeliveryError, send_gallery_invitation_email

from .models import AutomationExecution, AutomationRule


DEFAULT_RULES = (
    {
        "trigger": AutomationRule.Trigger.BOOKING_CONFIRMED,
        "action": AutomationRule.Action.SEND_CONTRACT,
        "name": "Send contract when booking is confirmed",
        "description": "Send an existing ready booking contract after the booking becomes confirmed.",
    },
    {
        "trigger": AutomationRule.Trigger.CONTRACT_SIGNED,
        "action": AutomationRule.Action.PREPARE_INVOICE,
        "name": "Prepare invoice when contract is signed",
        "description": "Create a draft invoice from the signed contract's booking value when no booking invoice exists yet.",
    },
    {
        "trigger": AutomationRule.Trigger.INVOICE_DUE,
        "action": AutomationRule.Action.SEND_INVOICE_REMINDER,
        "name": "Send invoice due reminder",
        "description": "Email the client three days before an unpaid sent invoice is due when invoice reminders are enabled.",
        "config": {"days_before": 3},
    },
    {
        "trigger": AutomationRule.Trigger.PAYMENT_RECEIVED,
        "action": AutomationRule.Action.COMPLETE_FINANCIAL_WORKFLOW,
        "name": "Complete workflow when invoice is paid",
        "description": "Record completion in automation history when an invoice reaches Paid.",
    },
    {
        "trigger": AutomationRule.Trigger.SHOOT_COMPLETED,
        "action": AutomationRule.Action.CREATE_GALLERY_TASK,
        "name": "Create gallery task when shoot is completed",
        "description": "Create a client task reminding the studio to prepare the gallery after a completed shoot.",
    },
    {
        "trigger": AutomationRule.Trigger.GALLERY_PUBLISHED,
        "action": AutomationRule.Action.NOTIFY_GALLERY_CLIENT,
        "name": "Notify client when gallery is published",
        "description": "Email existing gallery invitations with a fresh secure access link after publication.",
    },
    {
        "trigger": AutomationRule.Trigger.GALLERY_EXPIRING,
        "action": AutomationRule.Action.SEND_GALLERY_EXPIRATION_REMINDER,
        "name": "Send gallery expiration reminder",
        "description": "Email invited clients seven days before the gallery expires.",
        "config": {"days_before": 7},
    },
)


def ensure_default_rules(photographer):
    rules = []
    for definition in DEFAULT_RULES:
        config = definition.get("config", {})
        rule, created = AutomationRule.objects.get_or_create(
            photographer=photographer,
            trigger=definition["trigger"],
            action=definition["action"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "config": config,
                "enabled": False,
            },
        )
        if not created:
            changed = []
            for field, value in (("name", definition["name"]), ("description", definition["description"])):
                if getattr(rule, field) != value:
                    setattr(rule, field, value)
                    changed.append(field)
            if not rule.config and config:
                rule.config = config
                changed.append("config")
            if changed:
                rule.save(update_fields=[*changed, "updated_at"])
        rules.append(rule)
    return rules


def dispatch_event(*, trigger, photographer, target, event_key, context=None):
    ensure_default_rules(photographer)
    queued = []
    rules = AutomationRule.objects.filter(photographer=photographer, trigger=trigger, enabled=True)
    for rule in rules:
        try:
            execution, created = AutomationExecution.objects.get_or_create(
                rule=rule,
                event_key=event_key,
                defaults={
                    "photographer": photographer,
                    "trigger": trigger,
                    "target_type": target._meta.label_lower,
                    "target_id": target.pk,
                    "context": context or {},
                },
            )
        except IntegrityError:
            continue
        if not created:
            continue
        from .tasks import execute_automation
        transaction.on_commit(lambda execution_id=execution.pk: execute_automation.delay(execution_id))
        queued.append(execution)
    return queued


def _public_uri(path):
    base = settings.PUBLIC_BASE_URL or "http://localhost"
    return f"{base.rstrip('/')}{path}"


class _BackgroundRequest:
    def build_absolute_uri(self, path="/"):
        return _public_uri(path)


def _send_contract(execution, booking):
    contract = (
        Contract.objects.filter(
            photographer=execution.photographer,
            booking=booking,
            status=Contract.Status.READY,
        )
        .order_by("-created_at", "-pk")
        .first()
    )
    if not contract:
        return False, "No ready contract exists for this booking."
    send_contract_for_review(
        contract=contract,
        actor=execution.photographer.user,
        build_absolute_uri=lambda path: _public_uri(path),
    )
    return True, f"Contract {contract.pk} sent to the client."


def _prepare_invoice(execution, contract):
    booking = contract.booking
    existing = ClientInvoice.objects.filter(photographer=execution.photographer, booking=booking).first()
    if existing:
        return False, f"Invoice {existing.invoice_number or existing.pk} already exists for this booking."
    issue_date = timezone.localdate()
    amount = booking.booking_value
    with transaction.atomic():
        invoice = ClientInvoice.objects.create(
            photographer=execution.photographer,
            client=contract.client,
            booking=booking,
            invoice_number=next_invoice_number(execution.photographer),
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=30),
            payment_terms=30,
            subtotal=amount,
            total=amount,
            internal_notes="Prepared automatically after contract signature.",
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            item_type=InvoiceLineItem.ItemType.SESSION,
            description=f"{booking.session_type} photography service",
            quantity=1,
            unit_price=amount,
            subtotal=amount,
            total=amount,
            position=0,
        )
        InvoiceActivity.objects.create(
            photographer=execution.photographer,
            invoice=invoice,
            action="saved",
            description="Invoice prepared automatically after contract signature.",
        )
    return True, f"Draft invoice {invoice.invoice_number} prepared."


def _send_invoice_reminder(execution, invoice):
    if not invoice.reminders_enabled:
        return False, "Invoice reminders are disabled for this invoice."
    if invoice.status not in {ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID} or not invoice.sent_at:
        return False, "Invoice has not been sent to the client yet."
    if invoice.status in {ClientInvoice.Status.PAID, ClientInvoice.Status.VOID}:
        return False, "Invoice is already closed."
    if not invoice.client.email:
        return False, "Client has no email address."
    studio = execution.photographer.business_name or execution.photographer.display_name or execution.photographer.user.email
    balance = invoice.total - invoice.amount_paid
    message = EmailMultiAlternatives(
        f"Reminder: invoice {invoice.invoice_number} is due {invoice.due_date:%b %d, %Y}",
        f"Hi {invoice.client.first_name},\n\nThis is a reminder that invoice {invoice.invoice_number} from {studio} has a remaining balance of ${balance:.2f} and is due {invoice.due_date:%b %d, %Y}.\n\nThank you.",
        settings.DEFAULT_FROM_EMAIL,
        [invoice.client.email],
    )
    delivered = message.send(fail_silently=False)
    if delivered != 1:
        raise RuntimeError("Invoice reminder was not accepted by the email backend.")
    InvoiceActivity.objects.create(
        photographer=execution.photographer,
        invoice=invoice,
        action="reminder_sent",
        description="Invoice reminder sent by automation.",
    )
    return True, f"Invoice reminder sent to {invoice.client.email}."


def _create_gallery_task(execution, booking):
    if Gallery.objects.filter(photographer=execution.photographer, booking=booking).exists():
        return False, "A gallery is already linked to this booking."
    task, created = ClientTask.objects.get_or_create(
        photographer=execution.photographer,
        client=booking.client,
        title=f"Prepare gallery for {booking.session_type}",
        defaults={"priority": ClientTask.Priority.MEDIUM},
    )
    return (True, f"Gallery task {task.pk} created.") if created else (False, "Gallery task already exists.")


def _notify_gallery_client(execution, gallery):
    invitations = list(
        GalleryInvitation.objects.filter(gallery=gallery)
        .exclude(status=GalleryInvitation.Status.DISABLED)
        .exclude(email="")
    )
    if not invitations:
        return False, "No active gallery invitation is available to notify."
    sent = 0
    for invitation in invitations:
        token_record, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
        try:
            send_gallery_invitation_email(_BackgroundRequest(), invitation=invitation, raw_token=raw_token)
        except GalleryInvitationDeliveryError:
            token_record.revoked_at = timezone.now()
            token_record.save(update_fields=["revoked_at"])
            raise
        invitation.access_tokens.filter(revoked_at__isnull=True).exclude(pk=token_record.pk).update(revoked_at=timezone.now())
        invitation.status = GalleryInvitation.Status.PENDING
        invitation.resent_at = timezone.now()
        invitation.save(update_fields=["status", "resent_at"])
        log_gallery_activity(
            gallery=gallery,
            event_type=GalleryActivity.EventType.CLIENT_INVITED,
            description=f"Gallery publication automation emailed {invitation.client_name}.",
            actor=execution.photographer.user,
            related_object=invitation,
            metadata={"delivery": "email", "automation": True},
        )
        sent += 1
    return True, f"Secure gallery invitation sent to {sent} recipient(s)."


def _send_gallery_expiration_reminder(execution, gallery):
    recipients = sorted(set(
        GalleryInvitation.objects.filter(gallery=gallery)
        .exclude(status=GalleryInvitation.Status.DISABLED)
        .exclude(email="")
        .values_list("email", flat=True)
    ))
    if not recipients:
        return False, "No active invitation recipients are available."
    studio = execution.photographer.business_name or execution.photographer.display_name or execution.photographer.user.email
    delivered = EmailMultiAlternatives(
        f"Your {gallery.name} gallery expires soon",
        f"Your gallery from {studio} is scheduled to expire on {gallery.expires_at:%b %d, %Y}. Please download or save anything you need before then.",
        settings.DEFAULT_FROM_EMAIL,
        recipients,
    ).send(fail_silently=False)
    if delivered != 1:
        raise RuntimeError("Gallery expiration reminder was not accepted by the email backend.")
    return True, f"Gallery expiration reminder sent to {len(recipients)} recipient(s)."


def run_execution(execution):
    from apps.clients.models import ClientInvoice, ClientSession, Contract
    from apps.galleries.models import Gallery

    target_map = {
        "clients.clientsession": ClientSession,
        "clients.contract": Contract,
        "clients.clientinvoice": ClientInvoice,
        "galleries.gallery": Gallery,
    }
    model = target_map.get(execution.target_type)
    if not model:
        raise RuntimeError(f"Unsupported workflow target: {execution.target_type}")
    target = model.objects.filter(pk=execution.target_id, photographer=execution.photographer).first()
    if not target:
        return False, "Target record no longer exists in this workspace."

    handlers = {
        AutomationRule.Action.SEND_CONTRACT: _send_contract,
        AutomationRule.Action.PREPARE_INVOICE: _prepare_invoice,
        AutomationRule.Action.SEND_INVOICE_REMINDER: _send_invoice_reminder,
        AutomationRule.Action.COMPLETE_FINANCIAL_WORKFLOW: lambda execution, target: (True, "Paid invoice workflow completed."),
        AutomationRule.Action.CREATE_GALLERY_TASK: _create_gallery_task,
        AutomationRule.Action.NOTIFY_GALLERY_CLIENT: _notify_gallery_client,
        AutomationRule.Action.SEND_GALLERY_EXPIRATION_REMINDER: _send_gallery_expiration_reminder,
    }
    handler = handlers.get(execution.rule.action)
    if not handler:
        raise RuntimeError(f"Unsupported workflow action: {execution.rule.action}")
    return handler(execution, target)
