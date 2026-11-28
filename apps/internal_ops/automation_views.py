from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.automation.models import AutomationJob
from apps.automation.monitoring import snapshot
from apps.automation.recovery import retry_failed
from .decorators import internal_employee_required


@internal_employee_required
@require_GET
def automation_center(request):
    if not request.user.is_superuser or not request.user.is_active:
        raise PermissionDenied
    from apps.dashboard.financial_automation import financial_metrics
    jobs = AutomationJob.objects.order_by("-created_at", "-pk")
    status = request.GET.get("status", "")
    if status in AutomationJob.Status.values:
        jobs = jobs.filter(status=status)
    return render(request, "internal_ops/automation/center.html", {
        "employee": request.employee_profile, "is_internal_superuser": True,
        "financial_metrics": financial_metrics(), "metrics": snapshot(), "jobs": Paginator(jobs, 50).get_page(request.GET.get("page")),
        "statuses": AutomationJob.Status.choices, "selected_status": status,
    })


@internal_employee_required
@require_POST
def automation_retry(request, job_id):
    if not request.user.is_superuser or not request.user.is_active:
        raise PermissionDenied
    get_object_or_404(AutomationJob, pk=job_id)
    try:
        retry_failed(job_id=job_id, user=request.user, reason=request.POST.get("reason"))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Automation queued for retry.")
    return redirect("internal_ops:automation_center")


@internal_employee_required
@require_GET
def email_exceptions(request):
    if not request.user.is_superuser or not request.user.is_active:
        raise PermissionDenied
    from apps.notifications.models import EmailDelivery
    rows = EmailDelivery.objects.filter(status__in=["uncertain", "dead", "failed"]).order_by("-created_at", "-pk")
    return render(request, "internal_ops/automation/email_exceptions.html", {
        "employee": request.employee_profile, "is_internal_superuser": True,
        "deliveries": Paginator(rows, 50).get_page(request.GET.get("page")),
    })


@internal_employee_required
@require_POST
def email_resolve(request, delivery_id):
    if not request.user.is_superuser or not request.user.is_active:
        raise PermissionDenied
    from apps.notifications.models import EmailDelivery
    from apps.automation.email_recovery import resolve_email
    get_object_or_404(EmailDelivery, pk=delivery_id)
    try:
        resolve_email(delivery_id=delivery_id, user=request.user,
                      outcome=request.POST.get("outcome"), evidence=request.POST.get("evidence"))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Verified outcome recorded. No email was sent.")
    return redirect("internal_ops:email_exceptions")


@internal_employee_required
@require_GET
def email_operations(request):
    if not request.user.is_superuser or not request.user.is_active:
        raise PermissionDenied
    from datetime import timedelta
    from django.utils import timezone
    from apps.automation.email_monitoring import PERIODS, FILTERS, delivery_rows, filtered_rows, email_snapshot
    from apps.notifications.models import BrevoEmailEvent
    try:
        days = int(request.GET.get("days", 7))
    except (TypeError, ValueError):
        days = 7
    if days not in PERIODS:
        days = 7
    status = request.GET.get("status", "all")
    if status not in FILTERS:
        status = "all"
    now = timezone.now()
    metrics, events, event_types, backlog = email_snapshot(days, now)
    rows = filtered_rows(delivery_rows(days, now), status).order_by("-created_at", "-pk")
    from apps.notifications.business_reconciliation import snapshot as business_snapshot
    from apps.notifications.intents import missing_intents
    return render(request, "internal_ops/automation/email_operations.html", {
        "missing_intents": missing_intents().order_by("created_at")[:25],
        "missing_intent_count": missing_intents().count(),
        "business_missing": business_snapshot(),
        "employee": request.employee_profile, "is_internal_superuser": True,
        "days": days, "periods": PERIODS, "selected_status": status, "filters": FILTERS,
        "metrics": metrics, "events": events, "event_types": event_types, "backlog": backlog,
        "deliveries": Paginator(rows.prefetch_related("attempt_history"), 50).get_page(request.GET.get("page")),
        "recent_events": BrevoEmailEvent.objects.filter(received_at__gte=now-timedelta(days=days), received_at__lte=now).order_by("-received_at", "-pk")[:25],
    })


@internal_employee_required
@require_POST
def email_intent_cancel(request, intent_id):
    if not request.user.is_superuser or not request.user.is_active:
        raise PermissionDenied
    from apps.notifications.models import EmailIntent
    from apps.notifications.intents import cancel_missing_intent
    get_object_or_404(EmailIntent, pk=intent_id)
    try:
        cancel_missing_intent(intent_id=intent_id, user=request.user, reason=request.POST.get("reason"))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Intent cancelled with audit reason. No email sent.")
    return redirect("internal_ops:email_operations")
