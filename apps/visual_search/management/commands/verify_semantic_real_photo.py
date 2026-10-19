"""Real-photo semantic model and pgvector smoke test (isolated, rollback-only)."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify a real image, CLIP text/image embeddings, gallery isolation, and vector deletion without persisting test data."

    def add_arguments(self, parser):
        parser.add_argument("--image", required=True, help="Path to a consented real photograph")
        parser.add_argument("--query", required=True, help="Description expected to match the image")

    def handle(self, *args, **options):
        import numpy as np
        from pgvector.psycopg import register_vector
        from apps.visual_search.semantic import DIMENSION, embed_image, embed_text
        from apps.visual_search.vector_store import vector_connection

        path = Path(options["image"])
        if not path.is_file():
            raise CommandError("Image not found. Provide a local photograph with permission to process.")
        if not (2 <= len(options["query"].strip()) <= 200):
            raise CommandError("Query must be between 2 and 200 characters.")
        if not getattr(settings, "VISUAL_SEARCH_SEMANTIC_ENABLED", False):
            raise CommandError("Set VISUAL_SEARCH_SEMANTIC_ENABLED=true in the isolated test environment.")
        if not getattr(settings, "VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED", False):
            raise CommandError("Semantic policy approval flag is required for this isolated test.")
        if not getattr(settings, "VISUAL_SEARCH_SEMANTIC_MODEL_PATH", ""):
            raise CommandError("Set VISUAL_SEARCH_SEMANTIC_MODEL_PATH to an approved local CLIP model.")
        if not getattr(settings, "VISUAL_SEARCH_DATABASE_URL", ""):
            raise CommandError("VISUAL_SEARCH_DATABASE_URL must point to an isolated pgvector test database.")

        with path.open("rb") as stream:
            image_vector = np.asarray(embed_image(stream), dtype=np.float32)
        text_vector = np.asarray(embed_text(options["query"]), dtype=np.float32)
        for name, vector in (("image", image_vector), ("text", text_vector)):
            if vector.shape != (DIMENSION,) or not np.isfinite(vector).all():
                raise CommandError(f"{name} embedding is not a finite {DIMENSION}-dimensional vector")

        # All SQL is in an explicit transaction that is rolled back even on success.
        # Negative IDs avoid clashing with application-generated positive identifiers.
        with vector_connection() as conn:
            register_vector(conn)
            database = conn.execute("SELECT current_database()").fetchone()[0]
            if not any(word in database.lower() for word in ("test", "e2e", "scratch", "sandbox")):
                raise CommandError("Refusing to run on a database without a test/e2e/scratch/sandbox name.")
            class _RollbackSmoke(Exception):
                pass

            try:
                with conn.transaction():
                    photo_id = -9223372036854775000
                    gallery_id = -9223372036854775000
                    other_gallery_id = gallery_id + 1
                    conn.execute(
                        """INSERT INTO visual_search.app_semantic_embeddings
                           (photo_id, gallery_id, model_version, embedding)
                           VALUES (%s, %s, %s, %s)""",
                        (photo_id, gallery_id, "real-photo-smoke", image_vector),
                    )
                    result = conn.execute(
                        """SELECT photo_id, embedding <=> %s AS distance
                           FROM visual_search.app_semantic_embeddings
                           WHERE gallery_id = %s AND model_version = %s
                           ORDER BY embedding <=> %s LIMIT 1""",
                        (text_vector, gallery_id, "real-photo-smoke", text_vector),
                    ).fetchone()
                    if not result or result[0] != photo_id or not 0 <= float(result[1]) <= 2:
                        raise CommandError("Text-to-image vector lookup failed")
                    hidden = conn.execute(
                        "SELECT count(*) FROM visual_search.app_semantic_embeddings WHERE gallery_id = %s AND photo_id = %s",
                        (other_gallery_id, photo_id),
                    ).fetchone()[0]
                    if hidden:
                        raise CommandError("Gallery-scoped vector isolation failed")
                    conn.execute("DELETE FROM visual_search.app_semantic_embeddings WHERE photo_id = %s", (photo_id,))
                    remains = conn.execute(
                        "SELECT count(*) FROM visual_search.app_semantic_embeddings WHERE photo_id = %s", (photo_id,)
                    ).fetchone()[0]
                    if remains:
                        raise CommandError("Semantic vector deletion failed")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"PASS: real photo + text CLIP embeddings ({DIMENSION}d), pgvector search "
                            f"(cosine distance={float(result[1]):.4f}), gallery isolation, deletion."
                        )
                    )
                    self.stdout.write("No test vectors retained; transaction will be rolled back.")
                    raise _RollbackSmoke()
            except _RollbackSmoke:
                pass
            except CommandError:
                raise
            except Exception as exc:
                raise CommandError(f"Real-photo smoke test failed: {exc}") from exc
