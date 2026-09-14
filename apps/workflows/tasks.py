from datetime import datetime, time, timedelta

from celery import shared_task
from django.utils import timezone

from apps.clients.models import ClientInvoice
from apps.galleries.models import Gallery

from .models import AutomationExecution, AutomationRule
from .services import dispatch_event, run_execution


@shared_task
def execute_automation(execution_id):
    execution = AutomationExecution.objects.select_related("rule", "photographer").get(pk=execution_id)
    if execution.status in {
        AutomationExecution.Status.SUCCEEDED,
        AutomationExecution.Status.SKIPPED,
    }:
        return execution.status

    execution.status = AutomationExecution.Status.RUNNING
    execution.started_at = timezone.now()
    execution.error = ""
    execution.save(update_fields=["status", "started_at", "error"])

    try:
        performed, message = run_execution(execution)
    except Exception as exc:
        execution.status = AutomationExecution.Status.FAILED
        execution.error = str(exc)[:4000]
        execution.finished_at = timezone.now()
        execution.save(update_fields=["status", "error", "finished_at"])
        raise

    execution.status = (
        AutomationExecution.Status.SUCCEEDED if performed else AutomationExecution.Status.SKIPPED
    )
    execution.message = message[:500]
    execution.finished_at = timezone.now()
    execution.save(update_fields=["status", "message", "finished_at"])
    return execution.status


@shared_task
def scan_scheduled_automations():
    """Celery Beat entry point for date-driven launch automations."""
    today = timezone.localdate()

    invoice_rules = AutomationRule.objects.select_related("photographer").filter(
        trigger=AutomationRule.Trigger.INVOICE_DUE,
        enabled=True,
    )
    for rule in invoice_rules:
        days_before = int(rule.config.get("days_before", 3))
        due_date = today + timedelta(days=days_before)
        invoices = ClientInvoice.objects.filter(
            photographer=rule.photographer,
            due_date=due_date,
            reminders_enabled=True,
            sent_at__isnull=False,
            status__in=[ClientInvoice.Status.SENT, ClientInvoice.Status.PARTIALLY_PAID],
        )
        for invoice in invoices:
            dispatch_event(
                trigger=AutomationRule.Trigger.INVOICE_DUE,
                photographer=rule.photographer,
                target=invoice,
                event_key=f"invoice-due:{invoice.pk}:{due_date.isoformat()}",
                context={"due_date": due_date.isoformat(), "days_before": days_before},
            )

    gallery_rules = AutomationRule.objects.select_related("photographer").filter(
        trigger=AutomationRule.Trigger.GALLERY_EXPIRING,
        enabled=True,
    )
    for rule in gallery_rules:
        days_before = int(rule.config.get("days_before", 7))
        target_date = today + timedelta(days=days_before)
        start = timezone.make_aware(datetime.combine(target_date, time.min))
        end = start + timedelta(days=1)
        galleries = Gallery.objects.filter(
            photographer=rule.photographer,
            status__in=[Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED],
            expires_at__gte=start,
            expires_at__lt=end,
        )
        for gallery in galleries:
            dispatch_event(
                trigger=AutomationRule.Trigger.GALLERY_EXPIRING,
                photographer=rule.photographer,
                target=gallery,
                event_key=f"gallery-expiring:{gallery.pk}:{target_date.isoformat()}",
                context={"expiration_date": target_date.isoformat(), "days_before": days_before},
            )

    return "scheduled automation scan complete"
