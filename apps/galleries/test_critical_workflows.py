from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User

from .models import (
    AccessToken,
    Album,
    AlbumPhoto,
    Gallery,
    GalleryAnalyticsEvent,
    GalleryInvitation,
    GalleryPermission,
    GalleryPhoto,
    GalleryPhotoComment,
    GallerySettings,
)


MEDIA_SETTINGS = {
    "GALLERY_STORAGE_BACKEND": "local",
    "MEDIA_DELIVERY_BASE_URL": "https://media-test.lumispixel.test",
    "MEDIA_SIGNING_SECRET": "critical-workflow-test-secret",
    "MEDIA_SIGNED_URL_TTL": 900,
}


@override_settings(**MEDIA_SETTINGS)
class CriticalGalleryWorkflowTests(TestCase):
    """Fast integration coverage for the customer journey we cannot afford to break."""

    @classmethod
    def setUpTestData(cls):
        cls.owner_user = User.objects.create_user(
            email="critical-owner@example.com", password="testpass"
        )
        cls.owner = PhotographerProfile.objects.create(
            user=cls.owner_user, slug="critical-owner"
        )
        cls.other_user = User.objects.create_user(
            email="critical-other@example.com", password="testpass"
        )
        cls.other_owner = PhotographerProfile.objects.create(
            user=cls.other_user, slug="critical-other"
        )

    def setUp(self):
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Critical Wedding",
            slug="critical-wedding",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(
            gallery=self.gallery,
            download_images=True,
            favorite_photos=True,
            comment=True,
        )
        GallerySettings.objects.create(
            gallery=self.gallery,
            gallery_url=self.gallery.slug,
        )
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Critical Client",
            email="critical-client@example.com",
        )
        _, self.token = AccessToken.issue(self.invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile(
                "critical.jpg", b"critical-workflow-image", content_type="image/jpeg"
            ),
            original_name="critical.jpg",
            file_size=23,
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )

    def tearDown(self):
        for photo in GalleryPhoto.objects.filter(gallery=self.gallery):
            if photo.file:
                photo.file.delete(save=False)

    def test_published_gallery_album_and_photo_are_delivered_to_invited_client(self):
        album = Album.objects.create(
            gallery=self.gallery,
            name="Ceremony",
            visibility=Album.Visibility.CLIENT_ONLY,
        )
        AlbumPhoto.objects.create(album=album, photo=self.photo)

        response = self.client.get(
            reverse("galleries:client_gallery_access", args=[self.token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Critical Wedding")
        self.assertContains(response, "Ceremony")
        self.assertContains(response, f'id="photo-{self.photo.pk}"', html=False)
        self.assertContains(
            response,
            reverse(
                "galleries:client_gallery_media",
                args=[self.token, self.photo.pk],
            ),
        )

    def test_client_interactions_persist_and_are_visible_as_gallery_activity(self):
        favorite_url = reverse(
            "galleries:client_gallery_favorite", args=[self.token, self.photo.pk]
        )
        comment_url = reverse(
            "galleries:client_gallery_comment", args=[self.token, self.photo.pk]
        )
        download_url = reverse(
            "galleries:client_gallery_download", args=[self.token, self.photo.pk]
        )

        self.assertEqual(self.client.post(favorite_url).status_code, 200)
        self.assertIn(
            self.client.post(comment_url, {"comment": "Please keep this one."}).status_code,
            (200, 302),
        )
        self.assertEqual(self.client.get(download_url).status_code, 200)

        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.favorite_count, 1)
        self.assertTrue(
            GalleryPhotoComment.objects.filter(
                gallery=self.gallery,
                photo=self.photo,
                invitation=self.invitation,
                body="Please keep this one.",
            ).exists()
        )
        event_types = set(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                related_photo=self.photo,
            ).values_list("event_type", flat=True)
        )
        self.assertIn(GalleryAnalyticsEvent.EventType.FAVORITE, event_types)
        self.assertIn(GalleryAnalyticsEvent.EventType.COMMENT, event_types)
        self.assertIn(GalleryAnalyticsEvent.EventType.DOWNLOAD, event_types)

    def test_revoking_client_permissions_blocks_existing_token_actions(self):
        self.permissions.download_images = False
        self.permissions.favorite_photos = False
        self.permissions.comment = False
        self.permissions.save(
            update_fields=[
                "download_images",
                "favorite_photos",
                "comment",
                "updated_at",
            ]
        )

        self.assertEqual(
            self.client.post(
                reverse(
                    "galleries:client_gallery_favorite", args=[self.token, self.photo.pk]
                )
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "galleries:client_gallery_comment", args=[self.token, self.photo.pk]
                ),
                {"comment": "must not persist"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "galleries:client_gallery_download", args=[self.token, self.photo.pk]
                )
            ).status_code,
            403,
        )
        self.assertFalse(
            GalleryPhotoComment.objects.filter(body="must not persist").exists()
        )

    def test_client_token_cannot_cross_gallery_or_photographer_boundary(self):
        other_gallery = Gallery.objects.create(
            photographer=self.other_owner,
            name="Other Customer",
            slug="other-customer-critical",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        GalleryPermission.objects.create(
            gallery=other_gallery,
            download_images=True,
            favorite_photos=True,
            comment=True,
        )
        GallerySettings.objects.create(
            gallery=other_gallery, gallery_url=other_gallery.slug
        )
        other_photo = GalleryPhoto.objects.create(
            gallery=other_gallery,
            photographer=self.other_owner,
            file=SimpleUploadedFile(
                "other.jpg", b"other-customer-image", content_type="image/jpeg"
            ),
            original_name="other.jpg",
            file_size=20,
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )
        try:
            favorite = self.client.post(
                reverse(
                    "galleries:client_gallery_favorite",
                    args=[self.token, other_photo.pk],
                )
            )
            comment = self.client.post(
                reverse(
                    "galleries:client_gallery_comment",
                    args=[self.token, other_photo.pk],
                ),
                {"comment": "cross-tenant write"},
            )
            download = self.client.get(
                reverse(
                    "galleries:client_gallery_download",
                    args=[self.token, other_photo.pk],
                )
            )

            self.assertIn(favorite.status_code, (403, 404))
            self.assertIn(comment.status_code, (403, 404))
            self.assertIn(download.status_code, (403, 404))
            self.assertFalse(
                GalleryPhotoComment.objects.filter(
                    photo=other_photo, body="cross-tenant write"
                ).exists()
            )
            self.assertFalse(
                GalleryAnalyticsEvent.objects.filter(
                    gallery=other_gallery,
                    visitor_identifier=AccessToken.digest(self.token),
                ).exists()
            )
        finally:
            if other_photo.file:
                other_photo.file.delete(save=False)
