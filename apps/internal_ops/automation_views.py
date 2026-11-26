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
    jobs = AutomationJob.objects.order_by("-created_at", "-pk")
    status = request.GET.get("status", "")
    if status in AutomationJob.Status.values:
        jobs = jobs.filter(status=status)
    return render(request, "internal_ops/automation/center.html", {
        "employee": request.employee_profile, "is_internal_superuser": True,
        "metrics": snapshot(), "jobs": Paginator(jobs, 50).get_page(request.GET.get("page")),
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
