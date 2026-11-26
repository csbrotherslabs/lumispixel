from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.internal_ops.models import InternalAuditEvent
from apps.notifications.models import EmailDelivery


@transaction.atomic
def resolve_email(*, delivery_id, user, outcome, evidence):
    if not (user.is_authenticated and user.is_active and user.is_superuser):
        raise PermissionDenied
    evidence = (evidence or "").strip()
    if not evidence or len(evidence) > 500:
        raise ValidationError("Provide a provider verification reference (maximum 500 characters).")
    delivery = EmailDelivery.objects.select_for_update().get(pk=delivery_id)
    if delivery.status != EmailDelivery.Status.UNCERTAIN:
        raise ValidationError("Only uncertain deliveries can be resolved here.")
    if outcome not in ("accepted", "not_accepted"):
        raise ValidationError("Choose a verified provider outcome.")
    # Never reset the existing record or retry an ambiguous send automatically.
    # A confirmed non-acceptance is terminal; a separate intentional send can follow.
    delivery.status = EmailDelivery.Status.SENT if outcome == "accepted" else EmailDelivery.Status.DEAD
    delivery.sent_at = timezone.now() if outcome == "accepted" else None
    delivery.dead_at = timezone.now() if outcome == "not_accepted" else None
    delivery.next_attempt_at = None
    delivery.last_error = "" if outcome == "accepted" else "VerifiedNotAccepted"
    delivery.failure_kind = "" if outcome == "accepted" else EmailDelivery.FailureKind.PERMANENT
    delivery.save(update_fields=["status", "sent_at", "dead_at", "next_attempt_at", "last_error", "failure_kind"])
    InternalAuditEvent.objects.create(
        actor=getattr(user, "employee_profile", None),
        category=InternalAuditEvent.Category.SYSTEM, action="automation.email.resolve",
        target_type="email_delivery", target_id=str(delivery.pk),
        summary="Operator recorded verified email outcome", reason=evidence,
        metadata={"user_id": str(user.pk), "outcome": outcome, "attempts": delivery.attempt_count},
    )
    return delivery
