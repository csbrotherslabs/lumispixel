from celery import shared_task
from django.utils import timezone

from .models import AutomationJob
from .services import execute


@shared_task
def execute_job(job_id):
    return execute(job_id)


@shared_task
def scan_due_jobs():
    # PostgreSQL is the source of truth; repeated dispatch is safe.
    ids = list(AutomationJob.objects.filter(
        status__in=[AutomationJob.Status.PENDING, AutomationJob.Status.RETRY],
        available_at__lte=timezone.now(),
    ).order_by("available_at", "pk").values_list("pk", flat=True)[:200])
    for job_id in ids:
        execute_job.delay(job_id)
    return len(ids)


@shared_task
def reconcile_jobs():
    from .reconciliation import reconcile
    from apps.dashboard.financial_automation import scan_booking_reminders
    result = reconcile()
    result['booking_reminders_queued'] = scan_booking_reminders()
    return result
