import hashlib
import logging
import smtplib
from datetime import timedelta
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from .models import EmailDelivery, EmailAttempt
from . import brevo_transport

logger = logging.getLogger(__name__)
MAX_DELIVERY_ATTEMPTS = 6
BASE_RETRY_SECONDS = 60
MAX_RETRY_SECONDS = 60 * 60


class TransientDeliveryError(Exception):
    pass


class PermanentDeliveryError(Exception):
    pass


def normalize_recipients(recipients):
    """Validate and deduplicate envelope recipients without leaking recipients via CC/BCC."""
    normalized = []
    seen = set()
    for raw in recipients:
        email = (raw or "").strip()
        if not email:
            continue
        # Reject header injection explicitly before Django constructs a message.
        if "\r" in email or "\n" in email:
            raise ValueError("Invalid email recipient")
        validate_email(email)
        key = email.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(email)
    return tuple(normalized)


def public_url(path=""):
    """Build links from the configured public origin, never from an untrusted Host header."""
    base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    parsed = urlparse(base)
    if not base or parsed.scheme not in ({"https"} if not settings.DEBUG else {"http", "https"}) or not parsed.netloc:
        raise ImproperlyConfigured("PUBLIC_BASE_URL must be an absolute trusted URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ImproperlyConfigured("PUBLIC_BASE_URL must be a clean origin")
    return urljoin(base + "/", str(path).lstrip("/"))


def safe_html_text(value):
    """Escape user-controlled values before interpolating them into HTML email."""
    return escape("" if value is None else str(value))


def delivery_key(*, event_key, recipients):
    normalized = ",".join(sorted({email.strip().lower() for email in recipients if email}))
    return hashlib.sha256(f"{event_key}|{normalized}".encode()).hexdigest()


def retry_delay(attempt_count):
    return min(BASE_RETRY_SECONDS * (2 ** min(6, max(attempt_count - 1, 0))), MAX_RETRY_SECONDS)


def classify_delivery_exception(exc):
    if isinstance(exc, brevo_transport.ProviderRejected):
        return EmailDelivery.FailureKind.PERMANENT
    if isinstance(exc, (brevo_transport.ProviderThrottled, brevo_transport.ProviderConfigurationError)):
        return EmailDelivery.FailureKind.TRANSIENT
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


@transaction.atomic
def queue_transactional_email(*, event_key, subject, plain_body, html_body="", recipients=(), expires_at=None, lifecycle_kind="", lifecycle_context=None, sensitive=False, supersession_scope=''):
    if sensitive and (not expires_at or not lifecycle_kind):
        raise ValueError("Sensitive email requires expiry and lifecycle guard")
    if expires_at and (timezone.is_naive(expires_at) or expires_at <= timezone.now()):
        raise ValueError("Email expiry must be a future aware timestamp")
    recipients = normalize_recipients(recipients)
    if not recipients:
        return None
    # Prevent newline/header injection in fields that become RFC email headers.
    if "\r" in subject or "\n" in subject:
        raise ValueError("Invalid email subject")
    from .intents import require_email
    intent = require_email(event_key=event_key, recipients=recipients, kind=lifecycle_kind)
    key = intent.key
    from .models import EmailSupersession
    from .payload_crypto import encrypt_payload
    scope = hashlib.sha256(supersession_scope.encode()).hexdigest() if supersession_scope else ''
    pointer = None
    if scope:
        pointer, _ = EmailSupersession.objects.select_for_update().get_or_create(scope=scope)
    encrypted = encrypt_payload(key, subject, plain_body, html_body) if sensitive else ''
    delivery, created = EmailDelivery.objects.get_or_create(
        idempotency_key=key,
        defaults={"event_key": event_key, "subject": "[encrypted]" if sensitive else subject, "plain_body": "" if sensitive else plain_body, "html_body": "" if sensitive else html_body, "encrypted_payload": encrypted, "supersession_scope": scope, "recipients": list(recipients), "expires_at": expires_at, "lifecycle_kind": lifecycle_kind, "lifecycle_context": lifecycle_context or {}, "sensitive": sensitive},
    )

    if delivery.supersession_scope != scope or delivery.sensitive != sensitive:
        raise ValueError('Email event policy mismatch')
    if pointer and created:
        EmailDelivery.objects.filter(supersession_scope=scope, status__in=['pending', 'retry']).exclude(pk=delivery.pk).update(status='cancelled', last_error='Superseded', next_attempt_at=None)
        pointer.current = delivery
        pointer.save(update_fields=['current'])

    if intent.delivery_id and intent.delivery_id != delivery.pk:
        raise ValueError('Email intent delivery mismatch')
    if not intent.delivery_id:
        intent.delivery = delivery
        intent.save(update_fields=['delivery'])

    def dispatch():
        from .tasks import deliver_transactional_email
        try:
            deliver_transactional_email.delay(delivery.pk)
        except Exception:
            logger.exception("Could not enqueue transactional email %s", delivery.pk)

    transaction.on_commit(dispatch)
    return delivery


def record_failure(delivery_id, exc, *, attempt_number=None):
    kind = classify_delivery_exception(exc)
    now = timezone.now()
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status != EmailDelivery.Status.SENDING or (attempt_number is not None and delivery.attempt_count != attempt_number):
            return delivery
        terminal = kind == EmailDelivery.FailureKind.PERMANENT or delivery.attempt_count >= delivery.attempt_limit
        delivery.failure_kind = kind
        delivery.last_error = type(exc).__name__[:2000]
        if not isinstance(exc, (brevo_transport.ProviderRejected, brevo_transport.ProviderThrottled, brevo_transport.ProviderConfigurationError, smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPResponseException)):
            delivery.status = EmailDelivery.Status.UNCERTAIN
            delivery.next_attempt_at = None
        elif terminal:
            delivery.status = EmailDelivery.Status.DEAD
            delivery.dead_at = now
            delivery.next_attempt_at = None
        else:
            delivery.status = EmailDelivery.Status.RETRY
            delivery.next_attempt_at = now + timedelta(seconds=max(retry_delay(delivery.attempt_count), getattr(exc, 'seconds', 0)))
        delivery.save(update_fields=("failure_kind", "last_error", "status", "dead_at", "next_attempt_at"))
        EmailAttempt.objects.filter(delivery=delivery, number=delivery.attempt_count, finished_at__isnull=True).update(finished_at=now, outcome=delivery.status, error_code=type(exc).__name__[:128])
        return delivery


def deliver_email(delivery_id):
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status not in (EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY):
            return False
        if delivery.next_attempt_at and delivery.next_attempt_at > timezone.now():
            return False
        from .lifecycle import check_before_claim
        if not check_before_claim(delivery, timezone.now()):
            return False
        from .payload_crypto import decrypt_payload
        try:
            subject, plain_body, html_body = decrypt_payload(delivery)
        except Exception:
            delivery.status = EmailDelivery.Status.RETRY
            delivery.last_error = 'PayloadDecryptionFailed'
            delivery.dead_at = None
            delivery.next_attempt_at = timezone.now() + timedelta(minutes=15)
            delivery.save(update_fields=['status', 'last_error', 'dead_at', 'next_attempt_at'])
            return False
        if delivery.attempt_count >= delivery.attempt_limit:
            delivery.status = EmailDelivery.Status.DEAD
            delivery.dead_at = timezone.now()
            delivery.last_error = "AttemptLimitReached"
            delivery.save(update_fields=["status", "dead_at", "last_error"])
            return False
        transport = settings.TRANSACTIONAL_EMAIL_TRANSPORT
        if transport not in ("smtp", "brevo") or (transport == "brevo" and not settings.BREVO_API_KEY):
            delivery.status = EmailDelivery.Status.RETRY
            delivery.last_error = "ProviderConfigurationError"
            delivery.next_attempt_at = timezone.now() + timedelta(minutes=15)
            delivery.save(update_fields=["status", "last_error", "next_attempt_at"])
            return False
        delivery.status = EmailDelivery.Status.SENDING
        delivery.attempt_count += 1
        delivery.last_attempt_at = timezone.now()
        delivery.next_attempt_at = None
        delivery.save(update_fields=("status", "attempt_count", "last_attempt_at", "next_attempt_at"))
        EmailAttempt.objects.create(delivery=delivery, number=delivery.attempt_count, started_at=delivery.last_attempt_at, transport=transport)
        attempt_number = delivery.attempt_count

    try:
        recipients = normalize_recipients(delivery.recipients)
        provider_message_id = ""
        if transport == "brevo":
            provider_message_id = brevo_transport.submit(subject=subject, plain_body=plain_body, html_body=html_body,
                recipients=recipients, correlation=f"lp:{delivery.idempotency_key}:{attempt_number}")
        else:
            message = EmailMultiAlternatives(subject=subject, body=plain_body, from_email=settings.DEFAULT_FROM_EMAIL, to=list(recipients), headers={"X-Mailin-custom": f"lp:{delivery.idempotency_key}"})
            if html_body:
                message.attach_alternative(html_body, "text/html")
            if message.send(fail_silently=False) != 1:
                raise RuntimeError("Email acceptance not confirmed")
    except Exception as exc:
        record_failure(delivery_id, exc, attempt_number=attempt_number)
        raise

    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
        EmailAttempt.objects.filter(delivery=delivery, number=attempt_number, provider_message_id="").update(provider_message_id=provider_message_id)
        if delivery.attempt_count == attempt_number and delivery.status in (EmailDelivery.Status.SENDING, EmailDelivery.Status.UNCERTAIN):
            delivery.status = EmailDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.failure_kind = EmailDelivery.FailureKind.NONE
            delivery.last_error = ""
            delivery.next_attempt_at = None
            delivery.save(update_fields=("status", "sent_at", "failure_kind", "last_error", "next_attempt_at"))
            EmailAttempt.objects.filter(delivery=delivery, number=attempt_number).update(finished_at=delivery.sent_at, outcome="sent", error_code="")
    return True
