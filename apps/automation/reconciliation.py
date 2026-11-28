"""Reconcile durable job state into the existing internal alert system."""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.internal_ops.models import SystemAlert
from apps.internal_ops.system_monitoring import _notify_alert
from .models import AutomationJob


@transaction.atomic
def sync_alert(*, key, count, severity, title, message):
    # get_or_create plus row lock serializes competing scans and notifications.
    alert, created = SystemAlert.objects.select_for_update().get_or_create(
        key=key, defaults={"component": "Automation", "severity": severity,
                           "title": title, "message": message,
                           "status": SystemAlert.Status.RESOLVED},
    )
    if not count:
        if created:
            alert.delete()
        elif alert.status != SystemAlert.Status.RESOLVED:
            alert.status = SystemAlert.Status.RESOLVED
            alert.resolved_at = timezone.now()
            alert.resolved_by = None
            alert.save(update_fields=["status", "resolved_at", "resolved_by", "last_seen_at"])
        return
    notify = created or alert.status == SystemAlert.Status.RESOLVED or (
        alert.severity != SystemAlert.Severity.CRITICAL and severity == SystemAlert.Severity.CRITICAL
    )
    if notify:
        alert.status = SystemAlert.Status.OPEN
        alert.acknowledged_at = None
        alert.acknowledged_by = None
    alert.severity = severity
    alert.title = title
    alert.message = message
    alert.metadata = {"job_count": count}
    alert.resolved_at = None
    alert.resolved_by = None
    alert.save()
    if notify:
        _notify_alert(alert, ["engineering"])


def reconcile():
    jobs = AutomationJob.objects.all()
    active = jobs.filter(status__in=[AutomationJob.Status.PENDING, AutomationJob.Status.RETRY])
    failed = jobs.filter(status=AutomationJob.Status.FAILED).count()
    overdue = active.filter(available_at__lt=timezone.now() - timedelta(minutes=15)).count()
    inconsistent = active.filter(attempts__gte=F("max_attempts")).count()
    from apps.notifications.models import EmailDelivery
    uncertain = EmailDelivery.objects.filter(status=EmailDelivery.Status.UNCERTAIN).count()
    dead = EmailDelivery.objects.filter(status__in=[EmailDelivery.Status.DEAD, EmailDelivery.Status.FAILED]).count()
    from apps.notifications.business_reconciliation import snapshot
    missing = snapshot()
    for item in missing:
        sync_alert(key='automation.missing_email.' + item['kind'], count=item['count'], severity='critical', title='Missing business email: ' + item['kind'], message=f"{item['count']} records lack expected outbox evidence. Review before any resend.")
    key_failures = EmailDelivery.objects.filter(status='retry', last_error='PayloadDecryptionFailed').count()
    from apps.workflows.models import AutomationExecution
    ambiguous = AutomationExecution.objects.filter(status="failed", error="LegacyExecutionOutcomeUnknown").count()
    from apps.notifications.intents import missing_intents
    checks = [
        ('automation.email_provider_configuration', EmailDelivery.objects.filter(status__in=['retry','dead'], last_error='ProviderConfigurationError').count(), 'critical', 'Email provider configuration failure', 'Verify provider credentials and sender configuration.'),
        ('automation.email_intent_missing', missing_intents().count(), 'critical', 'Required email intent has no delivery', 'Investigate business state; never automatically recreate a secure link.'),
        ("automation.workflow_ambiguous", ambiguous, "critical", "Legacy workflow outcome unknown", "Review business effects before any manual replay."),
        ('automation.email_key_failure', key_failures, 'critical', 'Email payload decryption blocked', 'Restore encryption keys before dispatch; do not regenerate secrets automatically.'),
        ("automation.email_uncertain", uncertain, "critical", "Email delivery outcome uncertain",
         "Verify provider acceptance before any resend."),
        ("automation.email_dead", dead, "critical", "Email deliveries exhausted or rejected",
         "Investigate delivery failures before recovery."),
        ("automation.failed", failed, "critical", "Automation jobs exhausted retries",
         "Review failed jobs in the Automation Center."),
        ("automation.overdue", overdue, "warning", "Automation dispatch overdue",
         "Jobs have been eligible for execution for more than 15 minutes. Check worker capacity and routing."),
        ("automation.inconsistent", inconsistent, "critical", "Automation retry state inconsistent",
         "Active jobs have exhausted their attempt allowance. Investigate before changing state."),
    ]
    for key, count, severity, title, detail in checks:
        sync_alert(key=key, count=count, severity=severity, title=title,
                   message=f"{count} affected jobs. {detail}")
    return {"failed": failed, "overdue": overdue, "inconsistent": inconsistent, "email_uncertain": uncertain, "email_dead": dead}
