"""Opt-in development-only selfie endpoint; never returns private-gallery hints."""
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .inference import extract_face_embeddings
from .search import find_public_matches

logger = logging.getLogger(__name__)


@login_required
@require_POST
def selfie_search(request):
    # Independent kill switch. Face indexing and selfie search are both off by default.
    if not (settings.VISUAL_SEARCH_FACE_INDEXING_ENABLED
            and getattr(settings, "VISUAL_SEARCH_SELFIE_API_ENABLED", False)):
        return JsonResponse({"error": "unavailable"}, status=503)
    if request.POST.get("biometric_search_consent") != "yes":
        return JsonResponse({"error": "consent_required"}, status=400)
    photo = request.FILES.get("selfie")
    if not photo or photo.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "invalid_selfie"}, status=400)
    if photo.content_type not in ("image/jpeg", "image/png", "image/webp"):
        return JsonResponse({"error": "invalid_selfie"}, status=400)
    try:
        vectors = extract_face_embeddings(photo)
        if len(vectors) != 1:
            return JsonResponse({"error": "exactly_one_face_required"}, status=400)
        matches = find_public_matches(vectors[0])
    except (ValueError, OSError):
        return JsonResponse({"error": "invalid_selfie"}, status=400)
    except Exception:
        logger.exception("Selfie search failed")
        return JsonResponse({"error": "search_unavailable"}, status=503)
    # No private-gallery identities, private match counts, photo identifiers or
    # selfie embeddings are returned or persisted.
    return JsonResponse({"results": matches})
