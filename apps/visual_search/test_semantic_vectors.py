"""Actual pgvector persistence; synthetic vectors are not CLIP quality proof."""
import os
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch
from django.test import TestCase, override_settings
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


@skipUnless(os.environ.get("VISUAL_SEARCH_INTEGRATION_DATABASE_URL"),
            "Requires the semantic integration environment with numpy and pgvector")
class SemanticClientResultLimitTests(TestCase):
    """Exercise the vector-client boundary separately from page-rendering tests."""

    def test_client_vector_results_retain_one_hundred_matches_in_rank_order(self):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import PhotographerProfile
        from apps.galleries.models import Gallery, GalleryPhoto
        from .semantic_api import _semantic_results

        user = get_user_model().objects.create_user(email="semantic-rank-limit@example.test", password="test")
        owner = PhotographerProfile.objects.create(user=user, slug="semantic-rank-limit")
        gallery = Gallery.objects.create(photographer=owner, name="Rank limit", slug="rank-limit")
        photos = GalleryPhoto.objects.bulk_create([GalleryPhoto(
            gallery=gallery, photographer=owner, file="test.jpg",
            status=GalleryPhoto.Status.COMPLETED, is_visible=True,
        ) for _ in range(100)])
        ranked = [photo.pk for photo in reversed(photos)]
        with patch("apps.visual_search.semantic.embed_text", return_value=[0.0] * 512), \
             patch("pgvector.psycopg.register_vector"), \
             patch("apps.visual_search.vector_store.vector_connection") as connection:
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
                (photo_id,) for photo_id in ranked
            ]
            self.assertEqual(_semantic_results(gallery, "people dancing"), ranked)
