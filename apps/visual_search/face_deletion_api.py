"""Photographer-mediated, gallery-scoped biometric erasure.

Only an explicitly linked CRM client can have a review presented to a
photographer. Photographer confirmation must identify an exact photo and face
slot. This API never performs similarity-based identity discovery.
"""
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.galleries.models import Gallery, GalleryPhoto
from .models import (
    ClientBiometricDeletionRequest, FaceDeletionReview, PhotographerDeletionAssessment, BiometricDeletionDiscoveryCandidate,
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

    ).distinct().order_by("requested_at")[:100]
    candidate_requests = ClientBiometricDeletionRequest.objects.filter(
        status__in=["pending", "in_review"],
        discovery_candidates__gallery__photographer__user=request.user,
    ).distinct().order_by("requested_at")[:100]
    requests = {item.pk: item for item in list(requests) + list(candidate_requests)}

    return JsonResponse({
        "requests": [
            {"request_id": item.pk, "requested_at": item.requested_at.isoformat(),
             "galleries": list(Gallery.objects.filter(
                 photographer__user=request.user,
             ).filter(
                 models.Q(client__user_id=item.user_id) |
                 models.Q(biometricdeletiondiscoverycandidate__request=item),
             ).distinct().values("id", "name")[:50])}
            for item in requests.values()
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
        
    ).first()
    if deletion is None or gallery is None or not _gallery_in_request_scope(deletion, gallery) or not GalleryPhoto.objects.filter(
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


@login_required
@require_GET
def photographer_face_review_photos(request, deletion_id, gallery_id):
    deletion = ClientBiometricDeletionRequest.objects.filter(
        pk=deletion_id, status__in=[
            ClientBiometricDeletionRequest.Status.PENDING,
            ClientBiometricDeletionRequest.Status.IN_REVIEW,
        ],
    ).first()
    gallery = Gallery.objects.filter(
        pk=gallery_id, photographer__user=request.user,
        
    ).first()
    if gallery is None or deletion is None or not _gallery_in_request_scope(deletion, gallery):
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse({
        "photos": list(GalleryPhoto.objects.filter(
            gallery=gallery,
        ).order_by("pk").values("id")[:100]),
    })


@login_required
@require_GET
def photographer_face_review_crops(request, deletion_id, photo_id):
    deletion = ClientBiometricDeletionRequest.objects.filter(
        pk=deletion_id, status__in=[
            ClientBiometricDeletionRequest.Status.PENDING,
            ClientBiometricDeletionRequest.Status.IN_REVIEW,
        ],
    ).first()
    photo = GalleryPhoto.objects.filter(
        pk=photo_id, gallery__photographer__user=request.user,
        gallery__
    ).first()
    if photo is None or deletion is None or not _gallery_in_request_scope(deletion, photo.gallery):
        return JsonResponse({"error": "not_found"}, status=404)
    if not getattr(settings, "VISUAL_SEARCH_FACE_DELETION_REVIEW_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    try:
        from .inference import extract_face_review_crops
        from .vector_store import verify_stored_face_slot
        with photo.file.open("rb") as stream:
            crops = extract_face_review_crops(stream)
        verified = [
            {"face_index": face["face_index"], "preview": face["preview"]}
            for face in crops
            if verify_stored_face_slot(
                photo_id=photo_id, face_index=face["face_index"],
                model_version=settings.VISUAL_SEARCH_FACE_MODEL_VERSION,
                vector=face["embedding"],
            )
        ]
        response = JsonResponse({"faces": verified})
        response["Cache-Control"] = "no-store"
        return response
    except Exception:
        logger.exception("Unable to render face review for photo %s", photo_id)
        return JsonResponse({"error": "review_unavailable"}, status=503)


@login_required
@require_POST
def photographer_assess_deletion(request, deletion_id):
    try:
        payload = json.loads(request.body)
        gallery_id = int(payload["gallery_id"])
        outcome = payload["outcome"]
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_request"}, status=400)
    if outcome not in ("unverified", "reviewed"):
        return JsonResponse({"error": "invalid_outcome"}, status=400)
    deletion = ClientBiometricDeletionRequest.objects.filter(
        pk=deletion_id, status__in=[
            ClientBiometricDeletionRequest.Status.PENDING,
            ClientBiometricDeletionRequest.Status.IN_REVIEW,
        ],
    ).first()
    gallery = Gallery.objects.filter(
        pk=gallery_id, photographer__user=request.user,
        
    ).first()
    if gallery is None:
        return JsonResponse({"error": "not_found"}, status=404)
    with transaction.atomic():
        PhotographerDeletionAssessment.objects.update_or_create(
            request=deletion, gallery=gallery,
            defaults={"photographer_user": request.user, "outcome": outcome},
        )
        if deletion.status == ClientBiometricDeletionRequest.Status.PENDING:
            deletion.status = ClientBiometricDeletionRequest.Status.IN_REVIEW
            deletion.save(update_fields=["status"])
    return JsonResponse({"outcome": outcome, "request_status": "in_review"})


def _gallery_in_request_scope(deletion, gallery):
    if gallery.client_id and gallery.client.user_id == deletion.user_id:
        return True
    return BiometricDeletionDiscoveryCandidate.objects.filter(
        request=deletion, gallery=gallery,
    ).exists()
