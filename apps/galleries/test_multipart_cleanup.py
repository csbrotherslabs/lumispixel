from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Gallery, GalleryMultipartUpload
from apps.galleries.tasks import cleanup_stale_multipart_uploads


@override_settings(B2_MULTIPART_STALE_AFTER_SECONDS=3600)
class StaleMultipartUploadCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="storage@example.com", password="test-pass-123")
        self.photographer = PhotographerProfile.objects.create(user=self.user)
        self.gallery = Gallery.objects.create(photographer=self.photographer, name="Storage Recovery")

    def session(self, *, age_hours=2, completed=False, aborted=False):
        upload = GalleryMultipartUpload.objects.create(
            gallery=self.gallery,
            photographer=self.photographer,
            object_key=f"private/test/galleries/{self.photographer.pk}/{self.gallery.pk}/originals/{GalleryMultipartUpload._meta.pk.default()}.jpg",
            upload_id="b2-upload-id",
            original_name="photo.jpg",
            content_type="image/jpeg",
            file_size=8 * 1024 * 1024,
            completed_at=timezone.now() if completed else None,
            aborted_at=timezone.now() if aborted else None,
        )
        GalleryMultipartUpload.objects.filter(pk=upload.pk).update(
            created_at=timezone.now() - timedelta(hours=age_hours)
        )
        upload.refresh_from_db()
        return upload

    @patch("apps.galleries.tasks.abort_multipart")
    def test_stale_active_upload_is_aborted_and_releases_reservation(self, abort):
        upload = self.session()
        result = cleanup_stale_multipart_uploads()
        upload.refresh_from_db()
        abort.assert_called_once_with(key=upload.object_key, upload_id=upload.upload_id)
        self.assertIsNotNone(upload.aborted_at)
        self.assertEqual(result, {"aborted": 1, "failed": 0})

    @patch("apps.galleries.tasks.abort_multipart")
    def test_recent_completed_and_already_aborted_uploads_are_ignored(self, abort):
        recent = self.session(age_hours=0)
        completed = self.session(completed=True)
        aborted = self.session(aborted=True)
        result = cleanup_stale_multipart_uploads()
        recent.refresh_from_db()
        completed.refresh_from_db()
        aborted.refresh_from_db()
        abort.assert_not_called()
        self.assertIsNone(recent.aborted_at)
        self.assertIsNotNone(completed.completed_at)
        self.assertIsNotNone(aborted.aborted_at)
        self.assertEqual(result, {"aborted": 0, "failed": 0})

    @patch("apps.galleries.tasks.abort_multipart", side_effect=RuntimeError("B2 unavailable"))
    def test_failed_storage_abort_stays_active_for_retry(self, abort):
        upload = self.session()
        result = cleanup_stale_multipart_uploads()
        upload.refresh_from_db()
        self.assertIsNone(upload.aborted_at)
        self.assertEqual(result, {"aborted": 0, "failed": 1})
