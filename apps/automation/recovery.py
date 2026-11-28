from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.internal_ops.models import InternalAuditEvent
from .models import AutomationJob
from .registry import definition


@transaction.atomic
def retry_failed(*, job_id, user, reason):
    # Initially restricted to active superusers; delegated roles require explicit policy.
    if not (user.is_authenticated and user.is_active and user.is_superuser):
        raise PermissionDenied("Automation recovery requires superuser access.")
    reason = (reason or "").strip()
    if not reason or len(reason) > 500:
        raise ValidationError("Provide a recovery reason of at most 500 characters.")
    job = AutomationJob.objects.select_for_update().get(pk=job_id)
    if job.status != AutomationJob.Status.FAILED:
        raise ValidationError("Only exhausted failed jobs can be retried.")
    try:
        spec = definition(job.kind)
    except KeyError:
        raise ValidationError("This automation handler is not registered.")
    previous_limit = job.max_attempts
    job.max_attempts = job.attempts + spec.max_attempts
    job.status = AutomationJob.Status.RETRY
    job.available_at = timezone.now()
    job.finished_at = None
    job.save(update_fields=["max_attempts", "status", "available_at", "finished_at"])
    InternalAuditEvent.objects.create(
        actor=getattr(user, "employee_profile", None),
        category=InternalAuditEvent.Category.SYSTEM,
        action="automation.retry",
        target_type="automation_job",
        target_id=str(job.pk),
        summary="Authorized retry of failed automation",
        reason=reason,
        metadata={"user_id": str(user.pk), "photographer_id": job.photographer_id,
                  "previous_limit": previous_limit, "new_limit": job.max_attempts,
                  "attempts": job.attempts},
    )
    return job
