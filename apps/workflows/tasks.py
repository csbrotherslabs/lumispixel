from datetime import datetime, time, timedelta

from celery import shared_task
from django.utils import timezone
from django.db import transaction

from apps.clients.models import ClientInvoice
from apps.galleries.models import Gallery

from .models import AutomationExecution, AutomationRule
from .services import dispatch_event, run_execution


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def execute_automation(execution_id):
    # Domain writes, outbox creation and completion commit atomically.
    try:
        with transaction.atomic():
            execution = AutomationExecution.objects.select_for_update().select_related("rule", "photographer").get(pk=execution_id)
            if execution.status in (AutomationExecution.Status.RUNNING, AutomationExecution.Status.SUCCEEDED, AutomationExecution.Status.SKIPPED):
                return execution.status
            if execution.error == "LegacyExecutionOutcomeUnknown":
                return execution.status
            execution.started_at = timezone.now()
            execution.error = ""
            if not execution.rule.enabled or execution.rule.photographer_id != execution.photographer_id:
                performed, message = False, "Workflow rule is disabled or unavailable."
            else:
                performed, message = run_execution(execution)
            execution.status = AutomationExecution.Status.SUCCEEDED if performed else AutomationExecution.Status.SKIPPED
            execution.message = message[:500]
            execution.finished_at = timezone.now()
            execution.save(update_fields=["status", "message", "started_at", "finished_at", "error"])
            return execution.status
    except Exception as exc:
        AutomationExecution.objects.filter(pk=execution_id).exclude(status__in=[
            AutomationExecution.Status.SUCCEEDED, AutomationExecution.Status.SKIPPED]).update(
            status=AutomationExecution.Status.FAILED, error=type(exc).__name__, finished_at=timezone.now())
        raise


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_jitter=True, max_retries=5)
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


@shared_task
def reconcile_workflow_dispatch(limit=100):
    """Recover never-started queued work; quarantine legacy ambiguous RUNNING rows."""
    from django.conf import settings
    import logging
    now = timezone.now()
    stale = now - timedelta(seconds=max(3600, settings.CELERY_TASK_TIME_LIMIT + 300))
    with transaction.atomic():
        rows = list(AutomationExecution.objects.select_for_update(skip_locked=True).filter(
            status=AutomationExecution.Status.RUNNING, started_at__lt=stale).order_by("pk")[:limit])
        for row in rows:
            row.status = AutomationExecution.Status.FAILED
            row.error = "LegacyExecutionOutcomeUnknown"
            row.finished_at = now
            row.save(update_fields=["status", "error", "finished_at"])
    ids = list(AutomationExecution.objects.filter(status=AutomationExecution.Status.QUEUED,
        queued_at__lt=now-timedelta(minutes=5)).order_by("queued_at").values_list("pk", flat=True)[:limit])
    for pk in ids:
        try:
            execute_automation.delay(pk)
        except Exception:
            logging.getLogger(__name__).error("Workflow dispatch failed for %s", pk)
    return len(ids)
