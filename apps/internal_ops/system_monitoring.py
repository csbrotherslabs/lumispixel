import logging

from django.conf import settings
from django.db import connection
from django.utils import timezone
from redis import Redis

from apps.galleries.storage import gallery_photo_storage
from apps.notifications.models import Notification
from apps.notifications.services import notify_user

from .models import EmployeeProfile, SupportTicket, SystemAlert


logger = logging.getLogger(__name__)
ACTIVE_TICKET_STATUSES = [SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS, SupportTicket.Status.WAITING_CUSTOMER]


def _internal_users(department_codes, include_executive=False):
    codes = set(department_codes)
    if include_executive:
        codes.add("executive")
    return [
        profile.user
        for profile in EmployeeProfile.objects.filter(
            status=EmployeeProfile.Status.ACTIVE,
            department__code__in=codes,
            department__is_active=True,
            user__is_active=True,
        ).select_related("user", "department")
        if profile.user.email
    ]


def _notify_alert(alert, department_codes):
    recipients = _internal_users(department_codes, include_executive=alert.severity == SystemAlert.Severity.CRITICAL)
    for user in recipients:
        notify_user(
            recipient=user,
            category=Notification.Category.SYSTEM,
            title=f"{alert.get_severity_display()}: {alert.title}",
            message=alert.message,
            action_url="/internal/system/",
            action_label="Open System Monitor",
            metadata={"system_alert_id": alert.pk, "system_alert_key": alert.key, "severity": alert.severity},
        )


def _upsert_alert(*, key, component, severity, title, message, metadata, departments):
    alert = SystemAlert.objects.filter(key=key).first()
    notify = False
    if alert is None:
        alert = SystemAlert.objects.create(
            key=key, component=component, severity=severity, title=title, message=message, metadata=metadata,
        )
        notify = True
    else:
        previous_severity = alert.severity
        previous_status = alert.status
        alert.component = component
        alert.severity = severity
        alert.title = title
        alert.message = message
        alert.metadata = metadata
        if previous_status == SystemAlert.Status.RESOLVED:
            alert.status = SystemAlert.Status.OPEN
        alert.resolved_at = None
        alert.resolved_by = None
        alert.save()
        notify = previous_status == SystemAlert.Status.RESOLVED or (
            previous_severity != SystemAlert.Severity.CRITICAL and severity == SystemAlert.Severity.CRITICAL
        )
    if notify:
        _notify_alert(alert, departments)
    return alert


def _resolve_alert(key):
    alert = SystemAlert.objects.filter(key=key).exclude(status=SystemAlert.Status.RESOLVED).first()
    if alert:
        alert.status = SystemAlert.Status.RESOLVED
        alert.resolved_at = timezone.now()
        alert.resolved_by = None
        alert.save(update_fields=["status", "resolved_at", "resolved_by", "last_seen_at"])
    return alert


def _result(key, component, healthy, label, detail, severity="info", value=None):
    return {"key": key, "component": component, "healthy": healthy, "label": label, "detail": detail, "severity": severity, "value": value}


def _dependency_result(*, results, key, component, label, check, healthy_detail, failure_title):
    try:
        check()
        results.append(_result(key, component, True, label, healthy_detail))
        _resolve_alert(key)
    except Exception as exc:
        # Do not interpolate provider exceptions: they can contain URLs, credentials,
        # object keys, or other production-sensitive details.
        logger.exception("Operational dependency check failed", extra={"dependency": component, "check_key": key})
        results.append(_result(key, component, False, label, f"{component} dependency check failed.", "critical"))
        try:
            _upsert_alert(
                key=key, component=component, severity=SystemAlert.Severity.CRITICAL,
                title=failure_title, message=f"The {component.lower()} production dependency did not respond to its health check.",
                metadata={"error_type": exc.__class__.__name__}, departments=["engineering"],
            )
        except Exception:
            logger.exception("Could not persist operational dependency alert", extra={"dependency": component, "check_key": key})


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _check_celery_broker():
    client = Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
    client.ping()


def _check_gallery_storage():
    if settings.GALLERY_STORAGE_BACKEND != "b2":
        return
    storage = gallery_photo_storage()
    # S3Storage exposes the underlying bucket lazily. Accessing its creation date
    # performs a read-only bucket metadata request without writing probe objects.
    storage.bucket.meta.client.head_bucket(Bucket=settings.B2_BUCKET_NAME)


def run_system_monitoring():
    results = []
    now = timezone.now()

    _dependency_result(
        results=results, key="platform.database", component="Database", label="Database connectivity",
        check=_check_database, healthy_detail="Database query completed successfully.", failure_title="Database connectivity failure",
    )
    _dependency_result(
        results=results, key="platform.celery_broker", component="Celery broker", label="Celery/Redis connectivity",
        check=_check_celery_broker, healthy_detail="Celery broker responded successfully.", failure_title="Celery broker connectivity failure",
    )
    _dependency_result(
        results=results, key="platform.gallery_storage", component="Gallery storage", label="B2 object storage connectivity",
        check=_check_gallery_storage,
        healthy_detail="B2 object storage responded successfully." if settings.GALLERY_STORAGE_BACKEND == "b2" else "Local gallery storage is active.",
        failure_title="Gallery storage connectivity failure",
    )

    active_tickets = SupportTicket.objects.filter(status__in=ACTIVE_TICKET_STATUSES)
    backlog = active_tickets.count()
    backlog_unhealthy = backlog >= 50
    backlog_severity = SystemAlert.Severity.CRITICAL if backlog >= 100 else SystemAlert.Severity.WARNING
    results.append(_result("support.backlog", "Support", not backlog_unhealthy, "Active ticket backlog", f"{backlog} active support tickets.", backlog_severity if backlog_unhealthy else "info", backlog))
    if backlog_unhealthy:
        _upsert_alert(key="support.backlog", component="Support", severity=backlog_severity, title="Support ticket backlog is elevated", message=f"There are {backlog} active support tickets. Review queue capacity and assignment.", metadata={"active_ticket_count": backlog, "warning_threshold": 50, "critical_threshold": 100}, departments=["customer-support"])
    else:
        _resolve_alert("support.backlog")

    overdue = active_tickets.filter(due_at__lt=now).count()
    overdue_unhealthy = overdue > 0
    overdue_severity = SystemAlert.Severity.CRITICAL if overdue >= 10 else SystemAlert.Severity.WARNING
    results.append(_result("support.overdue", "Support", not overdue_unhealthy, "Overdue tickets", f"{overdue} active tickets are past due.", overdue_severity if overdue_unhealthy else "info", overdue))
    if overdue_unhealthy:
        _upsert_alert(key="support.overdue", component="Support", severity=overdue_severity, title="Support tickets are overdue", message=f"{overdue} active support tickets are past their due date.", metadata={"overdue_ticket_count": overdue}, departments=["customer-support"])
    else:
        _resolve_alert("support.overdue")

    urgent_unassigned = active_tickets.filter(priority=SupportTicket.Priority.URGENT, assignee__isnull=True).count()
    urgent_unassigned_unhealthy = urgent_unassigned > 0
    urgent_severity = SystemAlert.Severity.CRITICAL if urgent_unassigned >= 5 else SystemAlert.Severity.WARNING
    results.append(_result("support.urgent_unassigned", "Support", not urgent_unassigned_unhealthy, "Urgent unassigned tickets", f"{urgent_unassigned} urgent tickets are unassigned.", urgent_severity if urgent_unassigned_unhealthy else "info", urgent_unassigned))
    if urgent_unassigned_unhealthy:
        _upsert_alert(key="support.urgent_unassigned", component="Support", severity=urgent_severity, title="Urgent tickets need assignment", message=f"{urgent_unassigned} urgent support tickets do not have an assignee.", metadata={"urgent_unassigned_count": urgent_unassigned}, departments=["customer-support"])
    else:
        _resolve_alert("support.urgent_unassigned")

    smtp_backend = "smtp" in getattr(settings, "EMAIL_BACKEND", "").lower()
    email_missing = smtp_backend and not all([getattr(settings, "EMAIL_HOST", ""), getattr(settings, "EMAIL_HOST_USER", ""), getattr(settings, "EMAIL_HOST_PASSWORD", "")])
    results.append(_result("platform.email_config", "Email", not email_missing, "Email delivery configuration", "SMTP credentials are configured." if not email_missing else "SMTP is enabled but one or more credentials are missing.", "warning" if email_missing else "info"))
    if email_missing:
        _upsert_alert(key="platform.email_config", component="Email", severity=SystemAlert.Severity.WARNING, title="Email delivery configuration is incomplete", message="SMTP is enabled but LumisPixel is missing one or more required email configuration values.", metadata={"backend": getattr(settings, "EMAIL_BACKEND", "")}, departments=["engineering"])
    else:
        _resolve_alert("platform.email_config")

    return results
