"""Isolated vector lookup for biometric erasure review, never client-facing."""
import math

from django.conf import settings


def discover_gallery_ids(embedding):
    import numpy as np
    from pgvector.psycopg import register_vector
    from .vector_store import vector_connection
    from .search import calibrated_max_distance
    from .models import FaceDeletionReview
    from apps.galleries.models import GalleryPhoto

    vector = np.asarray(embedding, dtype=np.float32)
    if vector.shape != (512,) or not np.isfinite(vector).all():
        raise ValueError("Invalid biometric probe")
    if not 0.99 <= float(np.linalg.norm(vector)) <= 1.01:
        raise ValueError("Biometric probe must be normalized")
    threshold = calibrated_max_distance()
    with vector_connection() as conn:
        register_vector(conn)
        rows = conn.execute(
            """SELECT photo_id, gallery_id, face_index
               FROM visual_search.app_face_embeddings
               WHERE model_version = %s AND (embedding <=> %s) <= %s
               ORDER BY embedding <=> %s ASC LIMIT 500""",
            (settings.VISUAL_SEARCH_FACE_MODEL_VERSION, vector, threshold, vector),
        ).fetchall()
    erased = set(FaceDeletionReview.objects.filter(
        photo_id__in=[row[0] for row in rows],
    ).values_list("photo_id", "face_index"))
    eligible = dict(GalleryPhoto.objects.filter(
        pk__in=[row[0] for row in rows],
        gallery__deleted_at__isnull=True,
        gallery__archived_at__isnull=True,
        gallery__face_search_policy__processing_authorized=True,
    ).values_list("pk", "gallery_id"))
    return sorted({
        gallery_id for photo_id, gallery_id, face_index in rows
        if (photo_id, face_index) not in erased
        and eligible.get(photo_id) == gallery_id
    })
