"""Persist obligations independently when a domain operation requires it."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import EmailIntent

@transaction.atomic
def require_email(*, event_key, recipients, kind=""):
    from .email_delivery import delivery_key, normalize_recipients
    addresses = normalize_recipients(recipients)
    if not addresses or not event_key or len(event_key) > 255:
        raise ValidationError("Valid event and recipient required.")
    key = delivery_key(event_key=event_key, recipients=addresses)
    intent, _ = EmailIntent.objects.select_for_update().get_or_create(key=key,
        defaults={"event_key": event_key, "kind": kind})
    if intent.cancelled_at or intent.event_key != event_key or intent.kind != kind:
        raise ValidationError("Email intent is cancelled or its policy changed.")
    return intent

def missing_intents():
    return EmailIntent.objects.filter(delivery__isnull=True, cancelled_at__isnull=True,
        created_at__lt=timezone.now()-timedelta(minutes=15))

@transaction.atomic
def cancel_missing_intent(*, intent_id, user, reason):
    if not (user.is_authenticated and user.is_active and user.is_superuser):
        raise PermissionDenied
    reason = (reason or "").strip()
    if not reason or len(reason) > 500:
        raise ValidationError("Provide a cancellation reason (maximum 500 characters).")
    intent = EmailIntent.objects.select_for_update().get(pk=intent_id)
    if intent.delivery_id or intent.cancelled_at:
        raise ValidationError("Only unresolved missing intents may be cancelled.")
    intent.cancelled_at = timezone.now()
    intent.cancelled_by = str(user.pk)
    intent.cancellation_reason = reason
    intent.save(update_fields=["cancelled_at", "cancelled_by", "cancellation_reason"])
    return intent
