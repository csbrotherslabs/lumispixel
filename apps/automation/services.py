"""Durable transactional job execution; external effects require a separate outbox."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import AutomationAttempt, AutomationJob
from .registry import definition


@transaction.atomic
def enqueue(*, photographer_id, kind, event_key, target_id):
    spec = definition(kind)
    if not event_key or len(event_key) > 255 or target_id <= 0:
        raise ValueError("Invalid automation identity")
    job, _ = AutomationJob.objects.get_or_create(
        photographer_id=photographer_id, kind=kind, event_key=event_key,
        defaults={"target_id": target_id, "max_attempts": spec.max_attempts},
    )
    if job.target_id != target_id:
        raise ValueError("Automation event identity collision")
    return job


@transaction.atomic
def execute(job_id):
    # Hold the row lock across the transactional handler and final status write.
    # A worker crash rolls back both the database effects and execution state.
    job = AutomationJob.objects.select_for_update().get(pk=job_id)
    if job.status not in (AutomationJob.Status.PENDING, AutomationJob.Status.RETRY) or job.available_at > timezone.now():
        return job.status
    if job.attempts >= job.max_attempts:
        job.status = AutomationJob.Status.FAILED
        job.error_code = "RetryBudgetExhausted"
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_code", "finished_at"])
        return job.status
    started = timezone.now()
    job.attempts += 1
    try:
        with transaction.atomic():
            definition(job.kind).handler(photographer_id=job.photographer_id, target_id=job.target_id)
    except Exception as exc:
        job.error_code = type(exc).__name__[:100]
        job.status = AutomationJob.Status.FAILED if job.attempts >= job.max_attempts else AutomationJob.Status.RETRY
        job.available_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** min(job.attempts - 1, 7)))
    else:
        job.status = AutomationJob.Status.SUCCEEDED
        job.error_code = ""
    finished = timezone.now()
    job.finished_at = finished if job.status in (AutomationJob.Status.SUCCEEDED, AutomationJob.Status.FAILED) else None
    job.save(update_fields=["attempts", "status", "available_at", "finished_at", "error_code"])
    AutomationAttempt.objects.create(job=job, number=job.attempts, started_at=started,
                                     finished_at=finished, outcome=job.status, error_code=job.error_code)
    return job.status
