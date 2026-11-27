"""Lifecycle checks for queued email; never claim recall of an external submission."""
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import EmailDelivery

QUEUED = (EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY)
TERMINAL = (EmailDelivery.Status.SENT, EmailDelivery.Status.DEAD, EmailDelivery.Status.FAILED,
            EmailDelivery.Status.CANCELLED, EmailDelivery.Status.EXPIRED)


def eligible(delivery):
    """Explicit allowlist of domain checks; unknown kinds fail closed."""
    if not delivery.lifecycle_kind:
        return not delivery.sensitive
    if delivery.lifecycle_kind == "account.verify":
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(pk=delivery.lifecycle_context.get("user_id"), is_active=True).first()
        if not user or user.email_verified:
            return False
        # Token is in the existing payload, never duplicated in lifecycle metadata.
        from django.utils.crypto import salted_hmac
        state = salted_hmac("email-lifecycle-account", str(user.pk) + "|" + user.email + "|" + str(user.password) + "|" + str(getattr(user, "email_verified_at", ""))).hexdigest()
        return state == delivery.lifecycle_context.get("state")
    return False


def stop_locked(delivery, status, reason):
    delivery.status = status
    delivery.last_error = reason
    delivery.next_attempt_at = None
    delivery.save(update_fields=["status", "last_error", "next_attempt_at"])


@transaction.atomic
def cancel_queued(*, delivery_id, event_key):
    """Caller must authorize the domain action and supply its exact event key."""
    delivery = EmailDelivery.objects.select_for_update().filter(pk=delivery_id, event_key=event_key).first()
    if not delivery or delivery.status not in QUEUED:
        return False
    stop_locked(delivery, EmailDelivery.Status.CANCELLED, "CancelledByDomain")
    return True


def check_before_claim(delivery, now):
    if delivery.expires_at and delivery.expires_at <= now:
        stop_locked(delivery, EmailDelivery.Status.EXPIRED, "ExpiredBeforeDispatch")
        return False
    from .models import EmailSupersession
    if delivery.supersession_scope and not EmailSupersession.objects.filter(scope=delivery.supersession_scope, current_id=delivery.pk).exists():
        stop_locked(delivery, EmailDelivery.Status.CANCELLED, 'Superseded')
        return False
    if delivery.payload_purged_at or not eligible(delivery):
        stop_locked(delivery, EmailDelivery.Status.CANCELLED, "NoLongerEligible")
        return False
    return True


def purge_sensitive_payloads(limit=200):
    """Keep correlation and audit metadata; erase terminal sensitive message bodies."""
    now = timezone.now()
    ids = list(EmailDelivery.objects.filter(models.Q(status__in=TERMINAL) | models.Q(status=EmailDelivery.Status.UNCERTAIN, expires_at__lte=now)), sensitive=True, payload_purged_at__isnull=True).order_by("pk").values_list("pk", flat=True)[:limit])
    return EmailDelivery.objects.filter(models.Q(status__in=TERMINAL) | models.Q(status=EmailDelivery.Status.UNCERTAIN, expires_at__lte=now), pk__in=ids, sensitive=True, payload_purged_at__isnull=True).update(encrypted_payload='', plain_body="", html_body="", subject="[redacted]", lifecycle_context={}, payload_purged_at=now)
