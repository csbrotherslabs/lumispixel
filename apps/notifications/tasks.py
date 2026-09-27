import logging

from celery import shared_task
from django.utils import timezone

from .email_delivery import deliver_email, record_failure
from .models import EmailDelivery

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def deliver_transactional_email(self, delivery_id):
    try:
        return deliver_email(delivery_id)
    except Exception as exc:
        delivery = EmailDelivery.objects.filter(pk=delivery_id).first()
        if delivery and not delivery.last_error:
            # Keep the task boundary durable even when deliver_email is mocked or an
            # unexpected exception occurs before the delivery layer records failure.
            delivery = record_failure(delivery_id, exc)
        if not delivery or delivery.status == EmailDelivery.Status.DEAD:
            logger.error("Transactional email %s moved to dead letter: %s", delivery_id, exc)
            return False
        countdown = max(1, int((delivery.next_attempt_at - timezone.now()).total_seconds())) if delivery.next_attempt_at else 60
        logger.warning("Transactional email %s transiently failed; retry in %ss", delivery_id, countdown)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task
def reconcile_pending_transactional_emails(limit=100):
    now = timezone.now()
    ids = list(
        EmailDelivery.objects.filter(status__in=(EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY))
        .filter(next_attempt_at__isnull=True)
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )
    remaining = max(0, limit - len(ids))
    if remaining:
        ids += list(
            EmailDelivery.objects.filter(status=EmailDelivery.Status.RETRY, next_attempt_at__lte=now)
            .order_by("next_attempt_at", "created_at")
            .values_list("pk", flat=True)[:remaining]
        )
    for delivery_id in dict.fromkeys(ids):
        try:
            deliver_transactional_email.delay(delivery_id)
        except Exception:
            logger.exception("Could not enqueue recoverable transactional email %s", delivery_id)
    return len(set(ids))
