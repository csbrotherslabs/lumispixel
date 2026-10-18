"""Isolated PostgreSQL pgvector persistence; never queries the experimental tables."""

from contextlib import contextmanager
from django.conf import settings


@contextmanager
def vector_connection():
    if not settings.VISUAL_SEARCH_DATABASE_URL:
        raise RuntimeError("VISUAL_SEARCH_DATABASE_URL is required for face indexing")
    import psycopg
    with psycopg.connect(settings.VISUAL_SEARCH_DATABASE_URL, connect_timeout=10) as conn:
        yield conn


def replace_embeddings(*, photo_id, gallery_id, photographer_id, source_version, model_version, vectors):
    """Atomic replacement for one photo/version; schema created by setup command."""
    from pgvector.psycopg import register_vector
    import numpy as np

    with vector_connection() as conn:
        register_vector(conn)
        with conn.transaction():
            conn.execute(
                """DELETE FROM visual_search.app_face_embeddings
                   WHERE photo_id = %s""",
                (photo_id,),
            )
            for index, vector in enumerate(vectors):
                conn.execute(
                    """INSERT INTO visual_search.app_face_embeddings
                       (photo_id, gallery_id, photographer_id, source_version,
                        model_version, face_index, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (photo_id, gallery_id, photographer_id, source_version,
                     model_version, index, np.asarray(vector, dtype=np.float32)),
                )


def delete_photo_embeddings(photo_id):
    with vector_connection() as conn:
        conn.execute("DELETE FROM visual_search.app_face_embeddings WHERE photo_id = %s", (photo_id,))


def delete_gallery_embeddings(gallery_id):
    with vector_connection() as conn:
        conn.execute("DELETE FROM visual_search.app_face_embeddings WHERE gallery_id = %s", (gallery_id,))


def delete_confirmed_face(*, photo_id, face_index):
    """Delete one face slot, not the entire photograph or gallery.

    Returns affected row count. Caller must verify photographer ownership and
    subject identity separately; face_index alone is not identity evidence.
    """
    if not isinstance(face_index, int) or face_index < 0:
        raise ValueError("Invalid face index")
    with vector_connection() as conn:
        with conn.transaction():
            cursor = conn.execute(
                """DELETE FROM visual_search.app_face_embeddings
                   WHERE photo_id = %s AND face_index = %s""",
                (photo_id, face_index),
            )
            return cursor.rowcount
