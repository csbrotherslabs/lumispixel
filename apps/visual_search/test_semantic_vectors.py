"""Actual pgvector persistence; synthetic vectors are not CLIP quality proof."""
from types import SimpleNamespace
from django.test import override_settings
from . import test_integration


class SemanticVectorIntegrationTests(test_integration.VectorStoreIntegrationTests):
    def test_semantic_replace_and_purges_preserve_faces(self):
        import numpy as np
        from django.core.management import call_command
        from .semantic import replace_photo, purge_photo, purge_gallery
        from .vector_store import replace_embeddings, vector_connection
        with override_settings(VISUAL_SEARCH_DATABASE_URL=self.url):
            call_command("setup_semantic_vector_store")
            photo = SimpleNamespace(pk=self.photo_id, gallery_id=self.gallery_id)
            replace_embeddings(photo_id=self.photo_id, gallery_id=self.gallery_id,
                               photographer_id=self.photographer_id, source_version=1,
                               model_version="test", vectors=[np.ones(512)])
            try:
                for _ in range(2):
                    replace_photo(photo=photo, vector=np.ones(512))
                with vector_connection() as conn:
                    self.assertEqual(conn.execute("SELECT count(*) FROM visual_search.app_semantic_embeddings WHERE photo_id=%s", (self.photo_id,)).fetchone()[0], 1)
                purge_photo(self.photo_id)
                self.assertEqual(self._count(), 1)
                replace_photo(photo=photo, vector=np.ones(512))
                purge_gallery(self.gallery_id)
                with vector_connection() as conn:
                    self.assertEqual(conn.execute("SELECT count(*) FROM visual_search.app_semantic_embeddings WHERE gallery_id=%s", (self.gallery_id,)).fetchone()[0], 0)
                self.assertEqual(self._count(), 1)
            finally:
                purge_gallery(self.gallery_id)
