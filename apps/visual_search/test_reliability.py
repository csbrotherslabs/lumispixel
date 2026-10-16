"""Celery recovery and privacy regression tests.

These use an isolated Django test DB and mock the external vector connection.
Real pgvector writes remain covered by test_integration.py.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.visual_search.models import FaceIndexJob, GalleryFaceSearchPolicy
from apps.visual_search.signals import processing_revoked


class ConsentRevocationTests(TestCase):
    def test_revocation_cancels_jobs_and_purges_after_commit(self):
        policy = GalleryFaceSearchPolicy(
            gallery_id=987654321,
            processing_authorized=False,
            global_discovery_enabled=False,
        )
        with patch("apps.visual_search.signals.FaceIndexJob.objects.filter") as jobs, patch(
            "apps.visual_search.purges.enqueue_purge"
        ) as purge:
            with self.captureOnCommitCallbacks(execute=True):
                processing_revoked(sender=GalleryFaceSearchPolicy, instance=policy)
            jobs.assert_called_once_with(
                photo__gallery_id=policy.gallery_id,
                status__in=[FaceIndexJob.Status.PENDING, FaceIndexJob.Status.PROCESSING],
            )
            jobs.return_value.update.assert_called_once_with(
                status=FaceIndexJob.Status.CANCELLED
            )
            purge.assert_called_once_with("gallery", policy.gallery_id)

    def test_authorized_policy_does_not_purge(self):
        policy = GalleryFaceSearchPolicy(
            gallery_id=987654321,
            processing_authorized=True,
        )
        with patch("apps.visual_search.signals.FaceIndexJob.objects.filter") as jobs, patch(
            "apps.visual_search.signals._queue_purge"
        ) as purge:
            with self.captureOnCommitCallbacks(execute=True):
                processing_revoked(sender=GalleryFaceSearchPolicy, instance=policy)
            jobs.assert_not_called()
            purge.assert_not_called()


class WorkerRecoveryTests(TestCase):
    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=False,
        CELERY_TASK_TIME_LIMIT=60,
    )
    def test_stale_processing_job_recovered_without_dispatch(self):
        from apps.visual_search.maintenance import reconcile

        job = SimpleNamespace(
            status=FaceIndexJob.Status.PROCESSING,
            attempts=1,
            last_error="",
            save=MagicMock(),
        )
        with patch("apps.visual_search.vector_store.vector_connection") as connection, patch(
            "apps.visual_search.models.FaceIndexJob.objects.select_for_update"
        ) as locked, patch(
            "apps.visual_search.services.dispatch_face_index_job"
        ) as dispatch:
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
            locked.return_value.filter.return_value.__getitem__.return_value = [job]
            result = reconcile()
        self.assertEqual(result, {"removed_photo_vectors": 0, "recovered_jobs": 1})
        self.assertEqual(job.status, FaceIndexJob.Status.PENDING)
        self.assertEqual(job.last_error, "Worker interrupted or timed out")
        job.save.assert_called_once()
        dispatch.assert_not_called()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=False,
        CELERY_TASK_TIME_LIMIT=60,
    )
    def test_exhausted_processing_job_marked_failed(self):
        from apps.visual_search.maintenance import reconcile

        job = SimpleNamespace(
            status=FaceIndexJob.Status.PROCESSING,
            attempts=4,
            last_error="",
            save=MagicMock(),
        )
        with patch("apps.visual_search.vector_store.vector_connection") as connection, patch(
            "apps.visual_search.models.FaceIndexJob.objects.select_for_update"
        ) as locked:
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
            locked.return_value.filter.return_value.__getitem__.return_value = [job]
            result = reconcile()
        self.assertEqual(result["recovered_jobs"], 1)
        self.assertEqual(job.status, FaceIndexJob.Status.FAILED)

    @override_settings(VISUAL_SEARCH_FACE_INDEXING_ENABLED=False)
    def test_duplicate_delivery_cannot_claim_completed_job(self):
        from apps.visual_search.tasks import process_face_index_job

        with patch("apps.visual_search.tasks.FaceIndexJob.objects.select_for_update") as locked, patch(
            "apps.visual_search.inference.extract_face_embeddings"
        ) as inference:
            locked.return_value.select_related.return_value.filter.return_value.first.return_value = SimpleNamespace(
                status=FaceIndexJob.Status.COMPLETED
            )
            result = process_face_index_job.run(123456)
        self.assertEqual(result, "not_pending")
        inference.assert_not_called()
