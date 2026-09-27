from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PhotographerProfile
from apps.galleries.models import Gallery, GalleryPhoto, GalleryStorageDeletion


@override_settings(GALLERY_STORAGE_BACKEND="b2")
class BulkGalleryDeletionStorageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="bulk-delete@example.com", password="test-pass-123")
        self.photographer = PhotographerProfile.objects.create(user=self.user, onboarding_completed=True)
        self.gallery = Gallery.objects.create(photographer=self.photographer, name="Delete Me", slug="delete-me")
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.photographer,
            file="galleries/1/1/originals/photo.jpg",
            original_name="photo.jpg",
            file_size=100,
            status=GalleryPhoto.Status.COMPLETED,
        )
        self.client.force_login(self.user)

    @patch("apps.dashboard.views.process_storage_deletions")
    def test_bulk_gallery_delete_persists_cleanup_before_database_delete(self, process):
        gallery_id = self.gallery.pk
        object_key = self.photo.file.name

        response = self.client.post(
            reverse("photographer_workspace:gallery_actions"),
            {"gallery_ids": [gallery_id], "action": "delete"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Gallery.objects.filter(pk=gallery_id).exists())
        deletion = GalleryStorageDeletion.objects.get(object_key=object_key)
        self.assertEqual(deletion.storage_backend, GalleryStorageDeletion.Backend.B2)
        self.assertEqual(deletion.photographer_id, self.photographer.pk)
        self.assertEqual(deletion.gallery_id, gallery_id)
        self.assertIsNone(deletion.completed_at)
        process.assert_called_once_with()

    @patch("apps.galleries.storage_cleanup.delete_b2_object", side_effect=RuntimeError("B2 unavailable"))
    def test_failed_b2_delete_survives_gallery_database_delete_for_retry(self, delete_b2):
        gallery_id = self.gallery.pk
        object_key = self.photo.file.name

        response = self.client.post(
            reverse("photographer_workspace:gallery_actions"),
            {"gallery_ids": [gallery_id], "action": "delete"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Gallery.objects.filter(pk=gallery_id).exists())
        deletion = GalleryStorageDeletion.objects.get(object_key=object_key)
        self.assertIsNone(deletion.completed_at)
        self.assertEqual(deletion.attempts, 1)
        self.assertEqual(deletion.last_error, "RuntimeError")
