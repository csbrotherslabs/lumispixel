import hashlib
import logging
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import EmailDelivery

logger = logging.getLogger(__name__)
MAX_DELIVERY_ATTEMPTS = 6
BASE_RETRY_SECONDS = 60
MAX_RETRY_SECONDS = 60 * 60


class TransientDeliveryError(Exception):
    pass


class PermanentDeliveryError(Exception):
    pass


def delivery_key(*, event_key, recipients):
    normalized = ",".join(sorted({email.strip().lower() for email in recipients if email}))
    return hashlib.sha256(f"{event_key}|{normalized}".encode()).hexdigest()


def retry_delay(attempt_count):
    return min(BASE_RETRY_SECONDS * (2 ** max(attempt_count - 1, 0)), MAX_RETRY_SECONDS)


def classify_delivery_exception(exc):
    if isinstance(exc, (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused)):
        return EmailDelivery.FailureKind.PERMANENT
    if isinstance(exc, smtplib.SMTPResponseException):
        if 400 <= exc.smtp_code < 500:
            return EmailDelivery.FailureKind.TRANSIENT
        if 500 <= exc.smtp_code < 600:
            return EmailDelivery.FailureKind.PERMANENT
    if isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, ConnectionError, OSError)):
        return EmailDelivery.FailureKind.TRANSIENT
    return EmailDelivery.FailureKind.UNKNOWN


def queue_transactional_email(*, event_key, subject, plain_body, html_body="", recipients=()):
    recipients = tuple(dict.fromkeys(email.strip() for email in recipients if email and email.strip()))
    if not recipients:
        return None
    key = delivery_key(event_key=event_key, recipients=recipients)
    delivery, _ = EmailDelivery.objects.get_or_create(
        idempotency_key=key,
        defaults={"event_key": event_key, "subject": subject, "plain_body": plain_body, "html_body": html_body, "recipients": list(recipients)},
    )

    def dispatch():
        from .tasks import deliver_transactional_email
        try:
            deliver_transactional_email.delay(delivery.pk)
        except Exception:
            logger.exception("Could not enqueue transactional email %s", delivery.pk)

    transaction.on_commit(dispatch)
    return delivery


def record_failure(delivery_id, exc):
    kind = classify_delivery_exception(exc)
    now = timezone.now()
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status == EmailDelivery.Status.SENT:
            return delivery
        terminal = kind == EmailDelivery.FailureKind.PERMANENT or delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS
        delivery.failure_kind = kind
        delivery.last_error = str(exc)[:2000]
        if terminal:
            delivery.status = EmailDelivery.Status.DEAD
            delivery.dead_at = now
            delivery.next_attempt_at = None
        else:
            delivery.status = EmailDelivery.Status.RETRY
            delivery.next_attempt_at = now + timedelta(seconds=retry_delay(delivery.attempt_count))
        delivery.save(update_fields=("failure_kind", "last_error", "status", "dead_at", "next_attempt_at"))
        return delivery


def deliver_email(delivery_id):
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status in (EmailDelivery.Status.SENT, EmailDelivery.Status.DEAD):
            return False
        if delivery.next_attempt_at and delivery.next_attempt_at > timezone.now():
            return False
        delivery.attempt_count += 1
        delivery.last_attempt_at = timezone.now()
        delivery.next_attempt_at = None
        delivery.save(update_fields=("attempt_count", "last_attempt_at", "next_attempt_at"))

    message = EmailMultiAlternatives(subject=delivery.subject, body=delivery.plain_body, from_email=settings.DEFAULT_FROM_EMAIL, to=delivery.recipients)
    if delivery.html_body:
        message.attach_alternative(delivery.html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        record_failure(delivery_id, exc)
        raise

    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status != EmailDelivery.Status.SENT:
            delivery.status = EmailDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.failure_kind = EmailDelivery.FailureKind.NONE
            delivery.last_error = ""
            delivery.next_attempt_at = None
            delivery.save(update_fields=("status", "sent_at", "failure_kind", "last_error", "next_attempt_at"))
    return True
