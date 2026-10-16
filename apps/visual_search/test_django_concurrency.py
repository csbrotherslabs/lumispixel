"""Integration races against REAL Django models and PostgreSQL row locks.

Requires a disposable Django PostgreSQL test database. No real images, vector
writes, Celery broker, or research database access: inference and storage are
mocked, but ORM transactions and locking are real.
"""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import PhotographerProfile
from apps.galleries.models import Gallery, GalleryPhoto
from apps.visual_search.models import FaceIndexJob, FaceVectorPurge, GalleryFaceSearchPolicy
from apps.visual_search.tasks import process_face_index_job
from apps.visual_search.purges import execute_purge


@unittest.skipUnless(
    getattr(settings, "VISUAL_SEARCH_DJANGO_CONCURRENCY_TESTS", False),
    "Opt in with VISUAL_SEARCH_DJANGO_CONCURRENCY_TESTS=1 and disposable Django PostgreSQL test DB",
)
class DjangoModelConcurrencyTests(TransactionTestCase):
    """Thread workers use distinct connections and commit real ORM changes."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row locks required")
        user = get_user_model().objects.create(email=f"race-{uuid4().hex}@example.test")
        photographer = PhotographerProfile.objects.create(user=user, slug=f"race-{uuid4().hex}")
        self.gallery = Gallery.objects.create(
            photographer=photographer, name="Race test", slug=f"race-{uuid4().hex}"
        )
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=photographer,
            file="test/synthetic-race.jpg", original_name="synthetic-race.jpg",
            status=GalleryPhoto.Status.COMPLETED,
        )
        self.policy = GalleryFaceSearchPolicy.objects.create(
            gallery=self.gallery, processing_authorized=True,
        )
        self.job = FaceIndexJob.objects.create(
            photo=self.photo, source_key=self.photo.file.name
        )

    def _worker(self):
        close_old_connections()
        try:
            return process_face_index_job.run(self.job.pk)
        finally:
            connections.close_all()

    def _mock_processing(self, extract):
        return (
            patch("apps.visual_search.inference.extract_face_embeddings", side_effect=extract),
            patch("apps.visual_search.vector_store.replace_embeddings"),
            patch("django.db.models.fields.files.FieldFile.open", return_value=BytesIO(b"synthetic")),
        )

    @override_settings(VISUAL_SEARCH_FACE_INDEXING_ENABLED=True)
    def test_two_workers_only_one_claims_real_job(self):
        entered = threading.Event()
        release = threading.Event()
        def extract(_stream):
            entered.set()
            if not release.wait(15):
                raise TimeoutError("worker synchronization timed out")
            return []
        inference, vector, storage = self._mock_processing(extract)
        with inference, vector as write, storage:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self._worker)
                self.assertTrue(entered.wait(15))
                second = pool.submit(self._worker)
                self.assertEqual(second.result(timeout=15), "not_pending")
                release.set()
                self.assertEqual(first.result(timeout=15), {"faces": 0})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, FaceIndexJob.Status.COMPLETED)
        self.assertEqual(self.job.attempts, 1)
        write.assert_called_once()

    @override_settings(VISUAL_SEARCH_FACE_INDEXING_ENABLED=True)
    def test_reclaimed_job_rejects_old_worker_completion(self):
        entered = threading.Event()
        release = threading.Event()
        def extract(_stream):
            entered.set()
            if not release.wait(15):
                raise TimeoutError("worker synchronization timed out")
            return []
        inference, vector, storage = self._mock_processing(extract)
        with inference, vector as write, storage:
            with ThreadPoolExecutor(max_workers=1) as pool:
                old = pool.submit(self._worker)
                self.assertTrue(entered.wait(15))
                FaceIndexJob.objects.filter(pk=self.job.pk).update(
                    status=FaceIndexJob.Status.PENDING, claim_token=None,
                    started_at=timezone.now() - timedelta(hours=2),
                )
                release.set()
                self.assertEqual(old.result(timeout=15), "superseded")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, FaceIndexJob.Status.PENDING)
        write.assert_not_called()

    @override_settings(VISUAL_SEARCH_FACE_INDEXING_ENABLED=True)
    def test_revocation_during_inference_cancels_and_queues_purge(self):
        entered = threading.Event()
        release = threading.Event()
        def extract(_stream):
            entered.set()
            if not release.wait(15):
                raise TimeoutError("worker synchronization timed out")
            return []
        inference, vector, storage = self._mock_processing(extract)
        with inference, vector as write, storage, patch(
            "apps.visual_search.purges.dispatch_purge"
        ):
            with ThreadPoolExecutor(max_workers=1) as pool:
                worker = pool.submit(self._worker)
                self.assertTrue(entered.wait(15))
                self.policy.processing_authorized = False
                self.policy.save(update_fields=["processing_authorized", "updated_at"])
                release.set()
                self.assertIn(worker.result(timeout=15), ("superseded", "cancelled"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, FaceIndexJob.Status.CANCELLED)
        self.assertTrue(FaceVectorPurge.objects.filter(
            kind="gallery", object_id=self.gallery.pk,
            status=FaceVectorPurge.Status.PENDING,
        ).exists())
        write.assert_not_called()

    def test_purge_failure_then_recovery_on_real_record(self):
        purge = FaceVectorPurge.objects.create(kind="photo", object_id=self.photo.pk)
        with patch("apps.visual_search.vector_store.delete_photo_embeddings",
                   side_effect=OSError("simulated vector outage")):
            self.assertEqual(execute_purge(purge.pk), "retry_pending")
        purge.refresh_from_db()
        self.assertEqual(purge.status, FaceVectorPurge.Status.PENDING)
        with patch("apps.visual_search.vector_store.delete_photo_embeddings") as delete:
            self.assertEqual(execute_purge(purge.pk), "completed")
            delete.assert_called_once_with(self.photo.pk)
        purge.refresh_from_db()
        self.assertEqual(purge.status, FaceVectorPurge.Status.COMPLETED)
        self.assertEqual(purge.attempts, 2)
