"""Durable purge outbox and worker-claim regression tests."""
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

from apps.visual_search.models import FaceVectorPurge
from apps.visual_search.purges import enqueue_purge, execute_purge


class DurablePurgeTests(TestCase):
    def test_outbox_is_persisted_and_dispatched_only_after_commit(self):
        with patch("apps.visual_search.purges.dispatch_purge") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                record = enqueue_purge("photo", 55123)
                self.assertTrue(FaceVectorPurge.objects.filter(pk=record.pk).exists())
                dispatch.assert_not_called()
            dispatch.assert_called_once_with(record.pk)

    def test_failed_purge_is_retained_and_retry_succeeds(self):
        record = FaceVectorPurge.objects.create(kind="gallery", object_id=55124)
        with patch("apps.visual_search.vector_store.delete_gallery_embeddings", side_effect=OSError("temporary outage")):
            self.assertEqual(execute_purge(record.pk), "retry_pending")
        record.refresh_from_db()
        self.assertEqual(record.status, FaceVectorPurge.Status.PENDING)
        self.assertEqual(record.attempts, 1)
        with patch("apps.visual_search.vector_store.delete_gallery_embeddings") as delete:
            self.assertEqual(execute_purge(record.pk), "completed")
            self.assertEqual(execute_purge(record.pk), "already_completed")
            delete.assert_called_once_with(55124)
        record.refresh_from_db()
        self.assertEqual(record.status, FaceVectorPurge.Status.COMPLETED)
        self.assertEqual(record.attempts, 2)

    def test_processing_record_is_not_claimed_twice(self):
        record = FaceVectorPurge.objects.create(
            kind="photo", object_id=55125,
            status=FaceVectorPurge.Status.PROCESSING, claim_token=uuid4(),
        )
        with patch("apps.visual_search.vector_store.delete_photo_embeddings") as delete:
            self.assertEqual(execute_purge(record.pk), "already_processing")
            delete.assert_not_called()


class LifecyclePurgeTests(TestCase):
    """Archival and non-completed photos require durable deletion requests."""

    def test_archived_gallery_creates_outbox_before_dispatch(self):
        from types import SimpleNamespace
        from apps.galleries.models import Gallery
        from apps.visual_search.signals import gallery_inactive

        with patch("apps.visual_search.purges.dispatch_purge") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                gallery_inactive(
                    sender=Gallery,
                    instance=SimpleNamespace(pk=77321, archived_at="archived", deleted_at=None),
                )
                self.assertTrue(FaceVectorPurge.objects.filter(
                    kind="gallery", object_id=77321,
                    status=FaceVectorPurge.Status.PENDING,
                ).exists())
                dispatch.assert_not_called()
            dispatch.assert_called_once()

    def test_soft_deleted_gallery_creates_outbox(self):
        from types import SimpleNamespace
        from apps.galleries.models import Gallery
        from apps.visual_search.signals import gallery_inactive

        with patch("apps.visual_search.purges.dispatch_purge"):
            gallery_inactive(
                sender=Gallery,
                instance=SimpleNamespace(pk=77323, archived_at=None, deleted_at="deleted"),
            )
        self.assertTrue(FaceVectorPurge.objects.filter(
            kind="gallery", object_id=77323,
        ).exists())

    def test_inactive_photo_creates_outbox_before_dispatch(self):
        from types import SimpleNamespace
        from apps.galleries.models import GalleryPhoto
        from apps.visual_search.signals import photo_inactive

        with patch("apps.visual_search.purges.dispatch_purge") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                photo_inactive(
                    sender=GalleryPhoto,
                    instance=SimpleNamespace(pk=77322, status="failed"),
                )
                self.assertTrue(FaceVectorPurge.objects.filter(
                    kind="photo", object_id=77322,
                    status=FaceVectorPurge.Status.PENDING,
                ).exists())
                dispatch.assert_not_called()
            dispatch.assert_called_once()
