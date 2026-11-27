import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .email_delivery import deliver_email
from .models import EmailDelivery

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def deliver_transactional_email(self, delivery_id):
    try:
        return deliver_email(delivery_id)
    except Exception as exc:
        delivery = EmailDelivery.objects.filter(pk=delivery_id).first()
        # Only the claiming worker may classify its own attempt. Unexpected
        # interruptions are handled by the stale-claim reconciler.
        if not delivery or delivery.status != EmailDelivery.Status.RETRY:
            logger.error("Transactional email %s stopped automatic retries", delivery_id)
            return False
        countdown = max(1, int((delivery.next_attempt_at - timezone.now()).total_seconds())) if delivery.next_attempt_at else 60
        logger.warning("Transactional email %s transiently failed; retry in %ss", delivery_id, countdown)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task
def reconcile_pending_transactional_emails(limit=100):
    now = timezone.now()
    from django.conf import settings
    stale_before = now - timedelta(seconds=max(3600, settings.CELERY_TASK_TIME_LIMIT + 300))
    from django.db import transaction
    from .models import EmailAttempt
    with transaction.atomic():
        stale = list(EmailDelivery.objects.select_for_update(skip_locked=True).filter(
            status=EmailDelivery.Status.SENDING, last_attempt_at__lt=stale_before).order_by("pk")[:limit])
        for row in stale:
            row.status = EmailDelivery.Status.UNCERTAIN
            row.last_error = "WorkerOutcomeUnknown"
            row.next_attempt_at = None
            row.save(update_fields=["status", "last_error", "next_attempt_at"])
            EmailAttempt.objects.filter(delivery=row, number=row.attempt_count, finished_at__isnull=True).update(
                finished_at=now, outcome="uncertain", error_code="WorkerOutcomeUnknown")
    from .lifecycle import purge_sensitive_payloads
    EmailDelivery.objects.filter(status__in=[EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY], expires_at__lte=now).update(status=EmailDelivery.Status.EXPIRED, last_error="ExpiredBeforeDispatch", next_attempt_at=None)
    purge_sensitive_payloads()
    from .retention import purge_old_terminal_payloads
    purge_old_terminal_payloads(limit=limit)
    from django.db.models import Q
    from django.db.models.functions import Coalesce
    ids = list(EmailDelivery.objects.filter(status__in=(EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY))
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .annotate(eligible_at=Coalesce("next_attempt_at", "created_at"))
        .order_by("eligible_at", "pk").values_list("pk", flat=True)[:limit])
    for delivery_id in dict.fromkeys(ids):
        try:
            deliver_transactional_email.delay(delivery_id)
        except Exception:
            logger.exception("Could not enqueue recoverable transactional email %s", delivery_id)
    return len(set(ids))


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def scan_notification_reminders():
    from .reminders import scan_reminders
    scan_reminders()
