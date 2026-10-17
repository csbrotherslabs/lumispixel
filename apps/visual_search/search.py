"""Privacy-filtered, exact pgvector search. No private-gallery discovery."""
from django.conf import settings
from apps.galleries.models import Gallery, GalleryPhoto
from .models import GalleryFaceSearchPolicy
from .vector_store import vector_connection


def find_public_matches(embedding, *, limit=20):
    """Return public, published gallery IDs only after authoritative Django checks.

    Vector rows are untrusted hints: permissions are always rechecked in the
    application DB. Never expose private matches or counts.
    """
    import numpy as np
    from pgvector.psycopg import register_vector

    vector = np.asarray(embedding, dtype=np.float32)
    if vector.shape != (512,) or not np.isfinite(vector).all():
        raise ValueError("Invalid face vector")
    # Exact scan first. ANN recall and threshold calibration are separate work.
    threshold = float(getattr(settings, "VISUAL_SEARCH_SELFIE_MAX_DISTANCE", 0.35))
    if not 0 < threshold < 2:
        raise ValueError("Invalid selfie search threshold")
    model_version = settings.VISUAL_SEARCH_FACE_MODEL_VERSION
    with vector_connection() as conn:
        register_vector(conn)
        rows = conn.execute(
            """SELECT gallery_id, MIN(embedding <=> %s) AS distance
               FROM visual_search.app_face_embeddings
               WHERE model_version = %s
               GROUP BY gallery_id
               HAVING MIN(embedding <=> %s) <= %s
               ORDER BY distance ASC
               LIMIT %s""",
            (vector, model_version, vector, threshold, min(limit * 5, 100)),
        ).fetchall()
    candidate_ids = [gallery_id for gallery_id, _ in rows]
    eligible = set(Gallery.objects.filter(
        id__in=candidate_ids,
        status=Gallery.Status.PUBLISHED,
        visibility=Gallery.Visibility.PUBLIC,
        deleted_at__isnull=True,
        archived_at__isnull=True,
        face_search_policy__processing_authorized=True,
        face_search_policy__global_discovery_enabled=True,
        photos__status=GalleryPhoto.Status.COMPLETED,
    ).values_list("id", flat=True).distinct())
    return [{"gallery_id": gallery_id, "distance": float(distance)}
            for gallery_id, distance in rows if gallery_id in eligible][:limit]
