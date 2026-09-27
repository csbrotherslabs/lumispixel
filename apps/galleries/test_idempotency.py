from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Gallery, GalleryMultipartUpload, GalleryPhoto


class MultipartCompletionIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="idempotency@example.com", password="pass12345")
        self.studio = PhotographerProfile.objects.create(
            user=self.user, slug="idempotency", onboarding_completed=True
        )
        self.gallery = Gallery.objects.create(
            photographer=self.studio, name="Retry safe", slug="retry-safe"
        )
        self.session = GalleryMultipartUpload.objects.create(
            gallery=self.gallery,
            photographer=self.studio,
            object_key="private/dev/galleries/%s/%s/originals/retry.jpg" % (self.studio.pk, self.gallery.pk),
            upload_id="provider-upload-id",
            original_name="retry.jpg",
            content_type="image/jpeg",
            file_size=4,
        )
        self.client.force_login(self.user)

    def test_photo_has_unique_multipart_identity(self):
        first = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.studio,
            multipart_upload=self.session,
            file="galleries/retry.jpg",
            original_name="retry.jpg",
            file_size=4,
            status=GalleryPhoto.Status.COMPLETED,
        )
        self.session.completed_at = first.created_at
        self.session.save(update_fields=["completed_at"])

        response = self.client.post(
            reverse("photographer_workspace:gallery_multipart_complete", args=[self.session.pk]),
            data='{"parts":[{"part_number":1,"etag":"etag"}]}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["idempotent"])
        self.assertEqual(response.json()["photo"]["id"], first.pk)
        self.assertEqual(GalleryPhoto.objects.filter(multipart_upload=self.session).count(), 1)
