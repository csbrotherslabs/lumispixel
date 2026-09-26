import hashlib
import logging

from celery.exceptions import CeleryError
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import EmailDelivery

logger = logging.getLogger(__name__)


def delivery_key(*, event_key, recipients):
    normalized = ",".join(sorted({email.strip().lower() for email in recipients if email}))
    return hashlib.sha256(f"{event_key}|{normalized}".encode()).hexdigest()


def queue_transactional_email(*, event_key, subject, plain_body, html_body="", recipients=()):
    recipients = tuple(dict.fromkeys(email.strip() for email in recipients if email and email.strip()))
    if not recipients:
        return None
    key = delivery_key(event_key=event_key, recipients=recipients)
    delivery, _ = EmailDelivery.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "event_key": event_key,
            "subject": subject,
            "plain_body": plain_body,
            "html_body": html_body,
            "recipients": list(recipients),
        },
    )

    def dispatch():
        from .tasks import deliver_transactional_email
        try:
            deliver_transactional_email.delay(delivery.pk)
        except Exception:
            # Broker failure must never fail the originating user request. The durable
            # pending row remains available for a worker/reconciliation retry.
            logger.exception("Could not enqueue transactional email %s", delivery.pk)

    transaction.on_commit(dispatch)
    return delivery


def deliver_email(delivery_id):
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status == EmailDelivery.Status.SENT:
            return False
        delivery.attempt_count += 1
        delivery.last_attempt_at = timezone.now()
        delivery.save(update_fields=("attempt_count", "last_attempt_at"))

    message = EmailMultiAlternatives(
        subject=delivery.subject,
        body=delivery.plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=delivery.recipients,
    )
    if delivery.html_body:
        message.attach_alternative(delivery.html_body, "text/html")
    message.send(fail_silently=False)

    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status != EmailDelivery.Status.SENT:
            delivery.status = EmailDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.last_error = ""
            delivery.save(update_fields=("status", "sent_at", "last_error"))
    return True
