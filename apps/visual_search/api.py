"""Development-only selfie search with consent, throttling, and fail-closed gating."""
import hashlib
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .inference import extract_face_embeddings
from .search import find_public_matches

logger = logging.getLogger(__name__)
MAX_SELFIE_BYTES = 5 * 1024 * 1024


def _rate_limited(request):
    # Atomic cache.add: requires a SHARED cache backend for multi-worker safety.
    # Fail closed if the cache is unavailable.
    identity = str(request.user.pk)
    # Do not trust unverified X-Forwarded-For supplied by clients.
    remote = request.META.get("REMOTE_ADDR", "")
    digest = hashlib.sha256(f"{identity}:{remote}".encode()).hexdigest()
    window = int(getattr(settings, "VISUAL_SEARCH_SELFIE_RATE_WINDOW", 3600))
    quota = int(getattr(settings, "VISUAL_SEARCH_SELFIE_RATE_LIMIT", 5))
    if window < 60 or not 1 <= quota <= 100:
        raise RuntimeError("Invalid selfie rate limit configuration")
    # One atomic add per attempt; fixed-window bucket. At most quota successes
    # across a window, including concurrent requests.
    for slot in range(quota):
        if cache.add(f"selfie-search:{digest}:{slot}", 1, timeout=window):
            return False
    return True


@login_required
@require_POST
def selfie_search(request):
    if not (settings.VISUAL_SEARCH_FACE_INDEXING_ENABLED
            and getattr(settings, "VISUAL_SEARCH_SELFIE_API_ENABLED", False)):
        return JsonResponse({"error": "unavailable"}, status=503)
    if not getattr(settings, "VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    try:
        if _rate_limited(request):
            response = JsonResponse({"error": "rate_limited"}, status=429)
            response["Retry-After"] = str(getattr(settings, "VISUAL_SEARCH_SELFIE_RATE_WINDOW", 3600))
            return response
    except Exception:
        logger.exception("Selfie rate limiter unavailable")
        return JsonResponse({"error": "unavailable"}, status=503)
    if request.POST.get("biometric_search_consent") != "yes":
        return JsonResponse({"error": "consent_required"}, status=400)
    photo = request.FILES.get("selfie")
    if not photo or photo.size <= 0 or photo.size > MAX_SELFIE_BYTES:
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
    return JsonResponse({"results": matches})
