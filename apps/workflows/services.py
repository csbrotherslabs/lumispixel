from datetime import timedelta

from django.conf import settings
from apps.notifications.email_delivery import queue_transactional_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clients.contracts import send_contract_for_review
from apps.clients.models import ClientInvoice, ClientTask, Contract, InvoiceActivity, InvoiceLineItem
from apps.dashboard.invoices import next_invoice_number, queue_invoice_email
from apps.galleries.activity import log_gallery_activity
from apps.galleries.models import AccessToken, Gallery, GalleryActivity, GalleryInvitation
from apps.galleries.services import send_gallery_invitation_email

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
    return True, f"Contract {contract.pk} queued for the client."


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


@transaction.atomic
def _send_invoice_reminder(execution, invoice):
    invoice = ClientInvoice.objects.select_for_update().get(pk=invoice.pk, photographer=execution.photographer)
    if (not invoice.reminders_enabled or not invoice.sent_at or not invoice.due_date
            or invoice.status not in (ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID)
            or invoice.amount_paid >= invoice.total or not invoice.client.email):
        return False, "Invoice is no longer eligible for reminders."
    if execution.context.get("due_date") != invoice.due_date.isoformat():
        return False, "Invoice due date changed."
    delivery = queue_invoice_email(invoice, execution.photographer, purpose="reminder")
    InvoiceActivity.objects.create(photographer=execution.photographer, invoice=invoice,
        action="reminder_queued", description=f"Automation requested invoice reminder (delivery {delivery.pk}).")
    return True, f"Invoice reminder recorded; delivery {delivery.pk} ({delivery.status})."


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


def _eligible_gallery(gallery):
    return (gallery.status in (Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED)
        and not gallery.deleted_at and not gallery.archived_at
        and (not gallery.expires_at or gallery.expires_at > timezone.now()))


@transaction.atomic
def _notify_gallery_client(execution, gallery):
    gallery = Gallery.objects.select_for_update().get(pk=gallery.pk, photographer=execution.photographer)
    if not _eligible_gallery(gallery):
        return False, "Gallery is no longer available."
    invitations = GalleryInvitation.objects.select_for_update().filter(gallery=gallery,
        status__in=(GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE)).exclude(email="")
    count = 0
    for invitation in invitations:
        # The workflow execution and outbox records commit together.
        token_record, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
        send_gallery_invitation_email(_BackgroundRequest(), invitation=invitation, raw_token=raw_token)
        invitation.resent_at = timezone.now()
        invitation.save(update_fields=["resent_at"])
        log_gallery_activity(gallery=gallery, event_type=GalleryActivity.EventType.CLIENT_INVITED,
            description="Gallery publication automation queued an invitation.",
            actor=execution.photographer.user, related_object=invitation,
            metadata={"delivery": "queued", "automation": True, "execution_id": execution.pk})
        count += 1
    return bool(count), f"Secure gallery invitations queued for {count} recipient(s)."


@transaction.atomic
def _send_gallery_expiration_reminder(execution, gallery):
    gallery = Gallery.objects.select_for_update().get(pk=gallery.pk, photographer=execution.photographer)
    if not _eligible_gallery(gallery) or not gallery.expires_at:
        return False, "Gallery is no longer eligible for expiration reminders."
    if execution.context.get("expiration_date") != timezone.localtime(gallery.expires_at).date().isoformat():
        return False, "Gallery expiration date changed."
    studio = execution.photographer.business_name or execution.photographer.display_name or execution.photographer.user.email
    count = 0
    seen = set()
    for invitation in GalleryInvitation.objects.select_for_update().filter(gallery=gallery,
            status__in=(GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE)).exclude(email="").order_by("pk"):
        address = invitation.email.strip().casefold()
        if address in seen:
            continue
        seen.add(address)
        delivery = queue_transactional_email(
            event_key=f"workflow.gallery.expiry:{execution.pk}:{invitation.pk}",
            subject=f"Your {gallery.name} gallery expires soon",
            plain_body=f"Your gallery from {studio} is scheduled to expire on {gallery.expires_at:%b %d, %Y}. Please download or save anything you need before then.",
            recipients=[invitation.email], expires_at=gallery.expires_at,
            lifecycle_kind="gallery.expiry", lifecycle_context={"gallery_id": gallery.pk,
                "studio_id": gallery.photographer_id, "invitation_id": invitation.pk,
                "expires_at": gallery.expires_at.isoformat(), "execution_id": execution.pk})
        if delivery:
            count += 1
    return bool(count), f"Gallery expiration reminders recorded for {count} recipient(s)."


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
