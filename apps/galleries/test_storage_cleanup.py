from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.galleries.models import GalleryStorageDeletion
from apps.galleries.storage_cleanup import enqueue_storage_deletions, process_storage_deletions


@override_settings(GALLERY_STORAGE_BACKEND="b2")
class GalleryStorageDeletionTests(TestCase):
    def item(self, key="private/test/photo.jpg"):
        return {
            "storage_backend": "b2",
            "object_key": key,
            "photographer_id": 10,
            "gallery_id": 20,
        }

    def test_enqueue_is_idempotent(self):
        enqueue_storage_deletions([self.item(), self.item()])
        enqueue_storage_deletions([self.item()])
        self.assertEqual(GalleryStorageDeletion.objects.count(), 1)

    @patch("apps.galleries.storage_cleanup.delete_b2_object")
    def test_successful_cleanup_marks_object_complete(self, delete):
        enqueue_storage_deletions([self.item()])
        result = process_storage_deletions()
        record = GalleryStorageDeletion.objects.get()
        delete.assert_called_once_with(key="private/test/photo.jpg")
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.attempts, 1)
        self.assertEqual(result, {"completed": 1, "failed": 0, "exhausted": 0})

    @patch("apps.galleries.storage_cleanup.delete_b2_object", side_effect=RuntimeError("B2 unavailable"))
    def test_failed_cleanup_preserves_reference_for_retry(self, delete):
        enqueue_storage_deletions([self.item()])
        first = process_storage_deletions()
        record = GalleryStorageDeletion.objects.get()
        self.assertIsNone(record.completed_at)
        self.assertEqual(record.attempts, 1)
        self.assertEqual(record.last_error, "RuntimeError")
        self.assertEqual(first, {"completed": 0, "failed": 1, "exhausted": 0})

        delete.side_effect = None
        second = process_storage_deletions()
        record.refresh_from_db()
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.attempts, 2)
        self.assertEqual(second, {"completed": 1, "failed": 0})
