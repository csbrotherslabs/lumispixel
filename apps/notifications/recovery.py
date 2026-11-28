from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import EmailDelivery, EmailRecoveryEvent
from .lifecycle import eligible

@transaction.atomic
def requeue_dead(*, delivery_id, user, reason):
    if not user.is_active or not user.is_superuser:
        raise ValidationError("Active superuser required.")
    reason = (reason or "").strip()
    if not reason or len(reason) > 500:
        raise ValidationError("Provide a recovery reason, up to 500 characters.")
    row = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
    if (row.status != EmailDelivery.Status.DEAD or row.sensitive or row.payload_purged_at
            or row.supersession_scope or (row.expires_at and row.expires_at <= timezone.now())
            or not eligible(row)):
        raise ValidationError("Delivery is not eligible for manual retry.")
    EmailRecoveryEvent.objects.create(delivery=row, actor_id=str(user.pk), reason=reason,
        previous_attempt_limit=row.attempt_limit)
    row.attempt_limit = row.attempt_count + 1
    row.status = EmailDelivery.Status.PENDING
    row.next_attempt_at = None
    row.dead_at = None
    row.save(update_fields=["attempt_limit", "status", "next_attempt_at", "dead_at"])
    return row
