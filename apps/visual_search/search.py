"""Privacy-safe exact pgvector retrieval with per-photo authorization rechecks."""
import math

from django.conf import settings
from django.utils import timezone

from apps.galleries.models import Gallery, GalleryPhoto
from .vector_store import vector_connection


def calibrated_max_distance():
    """Fail closed until an explicitly validated model-specific threshold is set."""
    configured = getattr(settings, "VISUAL_SEARCH_SELFIE_MAX_DISTANCE", None)
    if configured in (None, ""):
        raise RuntimeError("Selfie similarity threshold has not been calibrated")
    try:
        threshold = float(configured)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid calibrated similarity threshold") from exc
    if not math.isfinite(threshold) or not 0 < threshold < 2:
        raise RuntimeError("Invalid calibrated similarity threshold")
    return threshold


def find_public_matches(embedding, *, limit=20):
    """Return public gallery identifiers only for eligible matched photos.

    No private gallery IDs are returned, even as candidate metadata. Search
    candidates are checked again against the authoritative Django database.
    """
    import numpy as np
    from pgvector.psycopg import register_vector

    vector = np.asarray(embedding, dtype=np.float32)
    if vector.shape != (512,) or not np.isfinite(vector).all():
        raise ValueError("Invalid face vector")
    norm = float(np.linalg.norm(vector))
    if not 0.99 <= norm <= 1.01:
        raise ValueError("Face vector must be normalized")
    threshold = calibrated_max_distance()
    limit = max(1, min(int(limit), 20))
    with vector_connection() as conn:
        register_vector(conn)
        rows = conn.execute(
            """SELECT photo_id, gallery_id, (embedding <=> %s) AS distance
               FROM visual_search.app_face_embeddings
               WHERE model_version = %s AND (embedding <=> %s) <= %s
               ORDER BY distance ASC
               LIMIT %s""",
            (vector, settings.VISUAL_SEARCH_FACE_MODEL_VERSION,
             vector, threshold, 500),
        ).fetchall()

    # Recheck exact photo membership, completion, visibility and gallery consent.
    # Never accept the gallery_id supplied by the vector database as authority.
    photo_ids = [photo_id for photo_id, _, _ in rows]
    allowed = dict(GalleryPhoto.objects.filter(
        pk__in=photo_ids,
        status=GalleryPhoto.Status.COMPLETED,
        is_visible=True,
        gallery__status=Gallery.Status.PUBLISHED,
        gallery__visibility=Gallery.Visibility.PUBLIC,
        gallery__published_at__isnull=False,
        gallery__deleted_at__isnull=True,
        gallery__archived_at__isnull=True,
        gallery__face_search_policy__processing_authorized=True,
        gallery__face_search_policy__global_discovery_enabled=True,
    ).filter(
        gallery__expires_at__isnull=True
    ).values_list("pk", "gallery_id"))
    # Expiring galleries may be eligible until expiry, but must not be disclosed
    # after their deadline. Query independently to avoid a cross-DB race.
    eligible_expiring = GalleryPhoto.objects.filter(
        pk__in=photo_ids,
        status=GalleryPhoto.Status.COMPLETED,
        is_visible=True,
        gallery__status=Gallery.Status.PUBLISHED,
        gallery__visibility=Gallery.Visibility.PUBLIC,
        gallery__published_at__isnull=False,
        gallery__deleted_at__isnull=True,
        gallery__archived_at__isnull=True,
        gallery__expires_at__gt=timezone.now(),
        gallery__face_search_policy__processing_authorized=True,
        gallery__face_search_policy__global_discovery_enabled=True,
    ).values_list("pk", "gallery_id")
    allowed.update(dict(eligible_expiring))
    seen = set()
    results = []
    for photo_id, gallery_id, distance in rows:
        actual_gallery = allowed.get(photo_id)
        if actual_gallery != gallery_id or actual_gallery in seen:
            continue
        if not math.isfinite(float(distance)) or float(distance) > threshold:
            continue
        seen.add(actual_gallery)
        # Distance is intentionally not exposed; biometric scores are internal.
        results.append({"gallery_id": actual_gallery})
        if len(results) >= limit:
            break
    return results
