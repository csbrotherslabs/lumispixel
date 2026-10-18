"""Photographer-mediated, gallery-scoped biometric erasure.

Only an explicitly linked CRM client can have a review presented to a
photographer. Photographer confirmation must identify an exact photo and face
slot. This API never performs similarity-based identity discovery.
"""
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse\nfrom django.shortcuts import render\nfrom django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.galleries.models import Gallery, GalleryPhoto
from .models import (
    ClientBiometricDeletionRequest, FaceDeletionReview,
)

logger = logging.getLogger(__name__)


@login_required
@require_GET
def photographer_face_deletion_inbox(request):
    requests = ClientBiometricDeletionRequest.objects.filter(
        status__in=[
            ClientBiometricDeletionRequest.Status.PENDING,
            ClientBiometricDeletionRequest.Status.IN_REVIEW,
        ],
        user__crm_client_records__galleries__photographer__user=request.user,
        user__crm_client_records__galleries__client__user__isnull=False,
    ).distinct().order_by("requested_at")[:100]
    return JsonResponse({
        "requests": [
            {"request_id": item.pk, "requested_at": item.requested_at.isoformat()}
            for item in requests
        ],
    })


@login_required
@require_POST
def photographer_confirm_face_deletion(request, deletion_id):
    # Never accept unverified face-slot guesses in customer environments.
    if not getattr(settings, "VISUAL_SEARCH_FACE_DELETION_REVIEW_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    try:
        data = json.loads(request.body)
        gallery_id = int(data["gallery_id"])
        photo_id = int(data["photo_id"])
        face_index = int(data["face_index"])
        if face_index < 0 or isinstance(data["face_index"], bool):
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_selection"}, status=400)

    deletion = ClientBiometricDeletionRequest.objects.filter(
        pk=deletion_id,
        status__in=[
            ClientBiometricDeletionRequest.Status.PENDING,
            ClientBiometricDeletionRequest.Status.IN_REVIEW,
        ],
    ).first()
    # This is deliberately limited to galleries linked to the authenticated
    # CRM client, not a speculative face search over all photographers.
    gallery = Gallery.objects.filter(
        pk=gallery_id,
        photographer__user=request.user,
        client__user_id=deletion.user_id if deletion else None,
    ).first()
    if deletion is None or gallery is None or not GalleryPhoto.objects.filter(
        pk=photo_id, gallery_id=gallery.pk,
    ).exists():
        return JsonResponse({"error": "not_found"}, status=404)

    with transaction.atomic():
        current = ClientBiometricDeletionRequest.objects.select_for_update().get(
            pk=deletion.pk,
        )
        if current.status == ClientBiometricDeletionRequest.Status.COMPLETED:
            return JsonResponse({"error": "request_closed"}, status=409)
        review, created = FaceDeletionReview.objects.get_or_create(
            request=current, gallery=gallery, photo_id=photo_id,
            face_index=face_index,
            defaults={"confirmed_by": request.user},
        )
        if not created and review.confirmed_by_id != request.user.pk:
            return JsonResponse({"error": "already_reviewed"}, status=409)
        if current.status == ClientBiometricDeletionRequest.Status.PENDING:
            current.status = ClientBiometricDeletionRequest.Status.IN_REVIEW
            current.save(update_fields=["status"])
    # Review is a durable suppression marker before touching the separate
    # vector database. Retry this exact endpoint if vector deletion fails.
    try:
        from .vector_store import delete_confirmed_face
        deleted_rows = delete_confirmed_face(
            photo_id=photo_id, face_index=face_index,
        )
    except Exception:
        logger.exception("Confirmed face erasure failed for review %s", review.pk)
        FaceDeletionReview.objects.filter(pk=review.pk).update(
            last_error="Vector deletion unavailable; retry required",
        )
        return JsonResponse({"error": "deletion_pending_retry"}, status=503)
    FaceDeletionReview.objects.filter(pk=review.pk).update(
        deleted_at=timezone.now(), last_error="",
    )
    return JsonResponse({
        "review_id": review.pk,
        "face_erased": True,
        "deleted_rows": deleted_rows,
        "request_status": "in_review",
    })


@login_required
@ensure_csrf_cookie
@require_GET
def photographer_face_deletion_page(request):
    return render(request, "visual_search/photographer_face_deletion.html")
