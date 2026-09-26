import logging

from celery import shared_task

from .email_delivery import deliver_email
from .models import EmailDelivery

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def deliver_transactional_email(self, delivery_id):
    try:
        return deliver_email(delivery_id)
    except Exception as exc:
        EmailDelivery.objects.filter(pk=delivery_id).update(last_error=str(exc)[:2000])
        logger.warning("Transactional email delivery %s failed; Celery will retry", delivery_id)
        raise


@shared_task
def reconcile_pending_transactional_emails(limit=100):
    ids = list(
        EmailDelivery.objects.filter(status=EmailDelivery.Status.PENDING)
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )
    for delivery_id in ids:
        try:
            deliver_transactional_email.delay(delivery_id)
        except Exception:
            # Keep the durable row pending for the next reconciliation pass.
            logger.exception("Could not enqueue pending transactional email %s", delivery_id)
    return len(ids)
