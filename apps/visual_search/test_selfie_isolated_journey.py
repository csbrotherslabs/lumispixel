"""Isolated HTTP -> inference -> pgvector adapter -> Django authorization tests.

Synthetic vectors only. Vector adapter is stubbed in these tests; the optional
real pgvector test suite is separate and requires a disposable database.
"""
from contextlib import contextmanager
from importlib.util import find_spec
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile
from apps.billing.models import Plan
from apps.galleries.models import Gallery, GalleryPhoto
from apps.visual_search.models import GalleryFaceSearchPolicy
from apps.visual_search.search import find_public_matches


class FakeVectorConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return self

    def fetchall(self):
        return self.rows


@unittest.skipUnless(find_spec("numpy") and find_spec("pgvector"),
                     "Requires optional numpy and pgvector packages")
class IsolatedSelfieSearchJourneyTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"name": "Free", "is_active": True})
        self.user = get_user_model().objects.create_user(
            email=f"search-{uuid4().hex}@example.test", password="test-password"
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user, slug=f"test-{uuid4().hex}"
        )
        self.client.force_login(self.user)
        self.url = reverse("visual_search:selfie")
        cache.clear()

    def tearDown(self):
        cache.clear()

    def gallery(self, *, visibility=Gallery.Visibility.PUBLIC, consent=True,
                discover=True, photo_visible=True, published=True,
                expired=False):
        now = timezone.now()
        gallery = Gallery.objects.create(
            photographer=self.photographer,
            name="Synthetic fixture", slug=f"fixture-{uuid4().hex}",
            status=Gallery.Status.PUBLISHED if published else Gallery.Status.DRAFT,
            visibility=visibility,
            published_at=now if published else None,
            expires_at=now + timedelta(days=-1 if expired else 1),
        )
        GalleryFaceSearchPolicy.objects.create(
            gallery=gallery,
            processing_authorized=consent,
            global_discovery_enabled=discover and consent,
        )
        photo = GalleryPhoto.objects.create(
            gallery=gallery,
            photographer=self.photographer,
            original_name="synthetic.jpg",
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=photo_visible,
        )
        return gallery, photo

    @override_settings(VISUAL_SEARCH_SELFIE_MAX_DISTANCE=0.4)
    def test_only_authorized_public_matched_photos_are_disclosed(self):
        allowed, a = self.gallery()
        private, b = self.gallery(visibility=Gallery.Visibility.PRIVATE)
        revoked, c = self.gallery(consent=False)
        hidden, d = self.gallery(photo_visible=False)
        expired, e = self.gallery(expired=True)
        unpublished, f = self.gallery(published=False)
        wrong, g = self.gallery()
        # Deliberately spoof a photo/gallery association in the vector database.
        rows = [
            (b.pk, private.pk, 0.01), (c.pk, revoked.pk, 0.02),
            (d.pk, hidden.pk, 0.03), (e.pk, expired.pk, 0.04),
            (f.pk, unpublished.pk, 0.05), (g.pk, private.pk, 0.06),
            (a.pk, allowed.pk, 0.1),
        ]
        connection = FakeVectorConnection(rows)

        @contextmanager
        def fake_connection():
            yield connection

        embedding = [1.0] + [0.0] * 511
        with patch("apps.visual_search.search.vector_connection", fake_connection), \
             patch("pgvector.psycopg.register_vector"):
            result = find_public_matches(embedding)
        self.assertEqual(result, [{"gallery_id": allowed.pk}])
        self.assertNotIn("distance", result[0])
        self.assertIn("model_version", connection.sql)

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
        VISUAL_SEARCH_SELFIE_MAX_DISTANCE=0.4,
    )
    def test_http_upload_through_real_authorization_query(self):
        allowed, photo = self.gallery()
        private, private_photo = self.gallery(visibility=Gallery.Visibility.PRIVATE)
        connection = FakeVectorConnection([
            (private_photo.pk, private.pk, 0.02),
            (photo.pk, allowed.pk, 0.1),
        ])

        @contextmanager
        def fake_connection():
            yield connection

        vector = [1.0] + [0.0] * 511
        with patch("apps.visual_search.api.extract_face_embeddings", return_value=[vector]), \
             patch("apps.visual_search.search.vector_connection", fake_connection), \
             patch("pgvector.psycopg.register_vector"):
            response = self.client.post(self.url, {
                "biometric_search_consent": "yes",
                "selfie": SimpleUploadedFile(
                    "synthetic.jpg", b"synthetic-only", content_type="image/jpeg"
                ),
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": [{"gallery_id": allowed.pk}]})

    @override_settings(VISUAL_SEARCH_SELFIE_MAX_DISTANCE=0.4)
    def test_revoked_consent_blocks_stale_vector_match(self):
        gallery, photo = self.gallery()
        policy = gallery.face_search_policy
        policy.processing_authorized = False
        with patch("apps.visual_search.purges.dispatch_purge"):
            policy.save()
        connection = FakeVectorConnection([(photo.pk, gallery.pk, 0.01)])

        @contextmanager
        def fake_connection():
            yield connection

        with patch("apps.visual_search.search.vector_connection", fake_connection), \
             patch("pgvector.psycopg.register_vector"):
            self.assertEqual(find_public_matches([1.0] + [0.0] * 511), [])
