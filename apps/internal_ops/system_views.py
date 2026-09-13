from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .decorators import internal_employee_required
from .models import InternalAuditEvent, SystemAlert
from .system_monitoring import run_system_monitoring


def _actor(request):
    return getattr(request, "employee_profile", None)


@internal_employee_required
@require_http_methods(["GET", "POST"])
def system_monitor(request):
    checks = None
    actor = _actor(request)
    if request.method == "POST" and request.POST.get("action") == "run_checks":
        checks = run_system_monitoring()
        InternalAuditEvent.objects.create(
            actor=actor,
            category=InternalAuditEvent.Category.SYSTEM,
            action="internal.system.checks.run",
            target_type="system_monitor",
            summary="Ran internal system monitoring checks",
            metadata={"check_count": len(checks), "superuser": request.user.is_superuser},
        )
        messages.success(request, "System checks completed.")

    alerts = SystemAlert.objects.select_related("acknowledged_by__user", "resolved_by__user")
    open_alerts = alerts.exclude(status=SystemAlert.Status.RESOLVED)
    context = {
        "employee": actor,
        "is_internal_superuser": request.user.is_superuser,
        "alerts": alerts[:100],
        "checks": checks,
        "open_count": open_alerts.count(),
        "critical_count": open_alerts.filter(severity=SystemAlert.Severity.CRITICAL).count(),
        "warning_count": open_alerts.filter(severity=SystemAlert.Severity.WARNING).count(),
        "resolved_count": alerts.filter(status=SystemAlert.Status.RESOLVED).count(),
    }
    return render(request, "internal_ops/system/monitor.html", context)


@internal_employee_required
@require_http_methods(["POST"])
def system_alert_action(request, alert_id):
    alert = get_object_or_404(SystemAlert, pk=alert_id)
    actor = _actor(request)
    action = request.POST.get("action")
    now = timezone.now()

    if action == "acknowledge" and alert.status != SystemAlert.Status.RESOLVED:
        alert.status = SystemAlert.Status.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.acknowledged_by = actor
        alert.save(update_fields=["status", "acknowledged_at", "acknowledged_by", "last_seen_at"])
        verb = "Acknowledged"
    elif action == "resolve":
        alert.status = SystemAlert.Status.RESOLVED
        alert.resolved_at = now
        alert.resolved_by = actor
        alert.save(update_fields=["status", "resolved_at", "resolved_by", "last_seen_at"])
        verb = "Resolved"
    elif action == "reopen":
        alert.status = SystemAlert.Status.OPEN
        alert.resolved_at = None
        alert.resolved_by = None
        alert.save(update_fields=["status", "resolved_at", "resolved_by", "last_seen_at"])
        verb = "Reopened"
    else:
        messages.error(request, "Unsupported alert action.")
        return redirect("internal_ops:system")

    InternalAuditEvent.objects.create(
        actor=actor,
        category=InternalAuditEvent.Category.SYSTEM,
        action=f"internal.system.alert.{action}",
        target_type="system_alert",
        target_id=str(alert.pk),
        summary=f"{verb} system alert {alert.key}",
        metadata={"alert_key": alert.key, "severity": alert.severity, "superuser": request.user.is_superuser},
    )
    messages.success(request, f"{verb} system alert.")
    return redirect("internal_ops:system")
