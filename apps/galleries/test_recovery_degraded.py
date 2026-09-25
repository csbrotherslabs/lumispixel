from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Gallery, GalleryMultipartUpload, GalleryStorageDeletion
from apps.galleries.storage_cleanup import process_storage_deletions
from apps.galleries.tasks import cleanup_stale_multipart_uploads


class RecoveryAndDegradedBehaviorTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="recovery@example.com", password="testpass")
        self.studio = PhotographerProfile.objects.create(user=user, slug="recovery-studio")
        self.gallery = Gallery.objects.create(photographer=self.studio, name="Recovery", slug="recovery")

    @override_settings(GALLERY_STORAGE_DELETION_MAX_ATTEMPTS=2)
    @patch("apps.galleries.storage_cleanup.delete_b2_object")
    def test_failed_storage_delete_remains_recoverable_until_budget_exhausted(self, delete_object):
        delete_object.side_effect = [RuntimeError("outage"), None]
        deletion = GalleryStorageDeletion.objects.create(
            storage_backend=GalleryStorageDeletion.Backend.B2,
            object_key="private/test/recovery.jpg",
            photographer_id=self.studio.pk,
            gallery_id=self.gallery.pk,
        )

        first = process_storage_deletions()
        deletion.refresh_from_db()
        self.assertEqual(first["failed"], 1)
        self.assertIsNone(deletion.completed_at)
        self.assertEqual(deletion.attempts, 1)

        second = process_storage_deletions()
        deletion.refresh_from_db()
        self.assertEqual(second["completed"], 1)
        self.assertIsNotNone(deletion.completed_at)
        self.assertEqual(deletion.attempts, 2)

    @override_settings(GALLERY_STORAGE_DELETION_MAX_ATTEMPTS=2)
    @patch("apps.galleries.storage_cleanup.delete_b2_object", side_effect=RuntimeError("outage"))
    def test_exhausted_storage_delete_is_quarantined_for_reconciliation(self, delete_object):
        deletion = GalleryStorageDeletion.objects.create(
            storage_backend=GalleryStorageDeletion.Backend.B2,
            object_key="private/test/poison.jpg",
        )
        process_storage_deletions()
        process_storage_deletions()
        third = process_storage_deletions()
        deletion.refresh_from_db()
        self.assertEqual(delete_object.call_count, 2)
        self.assertEqual(deletion.attempts, 2)
        self.assertIsNone(deletion.completed_at)
        self.assertEqual(third["exhausted"], 1)

    @patch("apps.galleries.tasks.abort_multipart")
    def test_failed_stale_abort_does_not_release_session_state(self, abort):
        abort.side_effect = RuntimeError("provider unavailable")
        session = GalleryMultipartUpload.objects.create(
            gallery=self.gallery,
            photographer=self.studio,
            object_key="private/test/stale.jpg",
            upload_id="upload-1",
            original_name="stale.jpg",
            content_type="image/jpeg",
            file_size=100,
        )
        GalleryMultipartUpload.objects.filter(pk=session.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=2)
        )

        result = cleanup_stale_multipart_uploads()
        session.refresh_from_db()
        self.assertEqual(result["failed"], 1)
        self.assertIsNone(session.aborted_at)
        self.assertIsNone(session.completed_at)
