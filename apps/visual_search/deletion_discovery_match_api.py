"""Private, deletion-only candidate discovery; never returns gallery identities.

Requires a separate client grant, explicit legal approval, photographer
processing authorization, and a calibrated model. No uploaded selfie is stored.
"""
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.galleries.models import Gallery
from .models import (
    ClientBiometricDeletionRequest, BiometricDeletionDiscoveryCandidate,
    BiometricDeletionDiscoveryGrant, GalleryFaceSearchPolicy,
)

logger = logging.getLogger(__name__)


@login_required
@require_POST
def discover_deletion_candidates(request):
    if not (
        getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_ENABLED", False)
        and getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_LEGAL_APPROVED", False)
        and getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_MATCHING_ENABLED", False)
    ):
        return JsonResponse({"error": "unavailable"}, status=503)
    item = ClientBiometricDeletionRequest.objects.filter(
        user=request.user, status__in=["pending", "in_review"],
    ).order_by("-requested_at").first()
    if item is None or not BiometricDeletionDiscoveryGrant.objects.filter(
        request=item, withdrawn_at__isnull=True,
        policy_version=getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_POLICY_VERSION", ""),
    ).exists():
        return JsonResponse({"error": "deletion_discovery_authorization_required"}, status=403)
    upload = request.FILES.get("selfie")
    if upload is None or upload.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "invalid_selfie"}, status=400)
    try:
        from .inference import extract_face_embeddings
        from .deletion_discovery_service import discover_gallery_ids
        vectors = extract_face_embeddings(upload)
        if len(vectors) != 1:
            return JsonResponse({"error": "one_face_required"}, status=400)
        gallery_ids = discover_gallery_ids(vectors[0])
        # Discovery never overrides a gallery owner's biometric-processing
        # permission. Private gallery IDs never leave this endpoint.
        authorized = GalleryFaceSearchPolicy.objects.filter(
            gallery_id__in=gallery_ids, processing_authorized=True,
        ).values_list("gallery_id", flat=True)
        notified_gallery_ids = []
        with transaction.atomic():
            grant = BiometricDeletionDiscoveryGrant.objects.select_for_update().get(
                request=item,
            )
            if grant.withdrawn_at or grant.policy_version != getattr(
                settings, "VISUAL_SEARCH_DELETION_DISCOVERY_POLICY_VERSION", "",
            ):
                return JsonResponse({"error": "authorization_withdrawn"}, status=403)
            for gallery_id in authorized:
                _, created = BiometricDeletionDiscoveryCandidate.objects.get_or_create(
                    request=item, gallery_id=gallery_id,
                )
                if created:
                    notified_gallery_ids.append(gallery_id)
            if item.status == ClientBiometricDeletionRequest.Status.PENDING:
                item.status = ClientBiometricDeletionRequest.Status.IN_REVIEW
                item.save(update_fields=["status"])
        if notified_gallery_ids:
            from .deletion_service import notify_photographers_for_candidates
            transaction.on_commit(lambda: notify_photographers_for_candidates(
                item.pk, notified_gallery_ids,
            ))
        return JsonResponse({
            "status": "review_pending",
            "message": "Eligible photographers will review potential matches.",
        }, status=202)
    except Exception:
        logger.exception("Deletion-only discovery failed for request %s", item.pk)
        return JsonResponse({"error": "discovery_unavailable"}, status=503)
