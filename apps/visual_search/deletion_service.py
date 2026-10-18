"""Durable deletion verification; never equate unverified identity with absence."""
from django.db import transaction
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
        # Explicit external scope reconciliation is required before closure.
        return False
