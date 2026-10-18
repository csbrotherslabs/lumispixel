"""Durable deletion verification; never equate unverified identity with absence."""
from django.db import transaction
from django.conf import settings
from django.core.mail import send_mail
from apps.galleries.models import Gallery
from django.utils import timezone

from .models import (
    ClientBiometricDeletionRequest, FaceDeletionReview,
    PhotographerDeletionAssessment, BiometricDeletionDiscoveryCandidate,
)


def retry_confirmed_erasure(review_id):
    """Idempotently erase one photographer-confirmed slot and verify absence."""
    from .vector_store import delete_confirmed_face, face_slot_exists
    review = FaceDeletionReview.objects.get(pk=review_id)
    if review.deleted_at:
        return "completed"
    try:
        delete_confirmed_face(photo_id=review.photo_id, face_index=review.face_index)
        if face_slot_exists(photo_id=review.photo_id, face_index=review.face_index):
            raise RuntimeError("Face slot still present after deletion")
    except Exception as exc:
        FaceDeletionReview.objects.filter(pk=review_id).update(
            last_error=str(exc)[:1000],
        )
        return "retry_required"
    FaceDeletionReview.objects.filter(pk=review_id).update(
        deleted_at=timezone.now(), last_error="",
    )
    return "completed"


def try_complete_deletion(request_id):
    """Close only after all known scopes reviewed and confirmed slots erased.

    This deliberately does not assert global completeness for unknown galleries.
    """
    with transaction.atomic():
        item = ClientBiometricDeletionRequest.objects.select_for_update().get(
            pk=request_id,
        )
        if item.status == ClientBiometricDeletionRequest.Status.COMPLETED:
            return True
        if FaceDeletionReview.objects.filter(
            request=item, deleted_at__isnull=True,
        ).exists():
            return False
        if PhotographerDeletionAssessment.objects.filter(
            request=item, outcome="unverified",
        ).exists():
            return False
        if BiometricDeletionDiscoveryCandidate.objects.filter(
            request=item, status__in=["pending", "unverified"],
        ).exists():
            return False
        if item.scope_verified_at is None or item.scope_verified_by_id is None:
            return False
        linked = Gallery.objects.filter(client__user_id=item.user_id)
        assessed = PhotographerDeletionAssessment.objects.filter(
            request=item, outcome="reviewed",
        ).values_list("gallery_id", flat=True)
        if linked.exclude(pk__in=assessed).exists():
            return False
        candidates = BiometricDeletionDiscoveryCandidate.objects.filter(request=item)
        if candidates.exclude(status="reviewed").exists():
            return False
        # Scope attestation explicitly documents what was and was not searched;
        # never represent an unknown gallery as verified absent.
        item.status = ClientBiometricDeletionRequest.Status.COMPLETED
        item.completed_at = timezone.now()
        item.save(update_fields=["status", "completed_at"])
        transaction.on_commit(lambda: send_deletion_notice(item.pk, "completed"))
        return True


def send_deletion_notice(request_id, event):
    """Send minimal privacy notification without gallery identities or biometrics."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        item = ClientBiometricDeletionRequest.objects.select_related("user").get(
            pk=request_id,
        )
        if not item.user.email:
            return False
        messages = {
            "requested": "We received your biometric deletion request. Selfie search has been disabled.",
            "completed": "Your reviewed biometric deletion request has been completed for the verified scope. Check your LumisPixel account for details.",
            "unverified": "A photographer could not verify your identity in a gallery. Your deletion request remains open.",
        }
        send_mail(
            "LumisPixel biometric privacy request",
            messages[event],
            settings.DEFAULT_FROM_EMAIL,
            [item.user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Unable to deliver biometric deletion notice %s", request_id)
        return False


def notify_photographers_for_candidates(request_id, gallery_ids):
    """Minimal owner-only review notification; never email gallery metadata."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        emails = list(Gallery.objects.filter(
            pk__in=gallery_ids,
        ).values_list("photographer__user__email", flat=True).distinct())
        for email in emails:
            if not email:
                continue
            try:
                send_mail(
                    "LumisPixel privacy review requested",
                    "A biometric deletion review is awaiting your confirmation. Sign in to LumisPixel and open your photographer privacy review inbox. Do not forward private gallery information.",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception("Photographer privacy notification failed for request %s", request_id)
    except Exception:
        logger.exception("Could not dispatch photographer notifications for request %s", request_id)
