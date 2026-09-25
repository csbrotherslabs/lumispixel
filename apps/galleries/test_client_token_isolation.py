"""Adversarial bearer-token isolation tests for delivered client galleries."""
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import (
    AccessToken, Gallery, GalleryAnalyticsEvent, GalleryInvitation,
    GalleryPermission, GalleryPhoto, GalleryPhotoComment,
)


class ClientGalleryTokenIsolationTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="token-owner@example.com", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.studio = PhotographerProfile.objects.create(
            user=owner, slug="token-isolation", onboarding_completed=True,
        )
        self.gallery_a = Gallery.objects.create(
            photographer=self.studio, name="Client A", slug="client-a",
            status=Gallery.Status.PUBLISHED,
        )
        self.gallery_b = Gallery.objects.create(
            photographer=self.studio, name="Client B", slug="client-b",
            status=Gallery.Status.PUBLISHED,
        )
        for gallery in (self.gallery_a, self.gallery_b):
            GalleryPermission.objects.create(
                gallery=gallery, view_gallery=True, favorite_photos=True,
                comment=True, download_images=True, download_originals=True,
            )
        self.photo_a = self._photo(self.gallery_a, "a.jpg")
        self.photo_b = self._photo(self.gallery_b, "b.jpg")
        self.invitation_a = GalleryInvitation.objects.create(
            gallery=self.gallery_a, client_name="Client A", email="a@example.com",
        )
        self.invitation_b = GalleryInvitation.objects.create(
            gallery=self.gallery_b, client_name="Client B", email="b@example.com",
        )
        self.token_a_record, self.token_a = AccessToken.issue(self.invitation_a)
        self.token_b_record, self.token_b = AccessToken.issue(self.invitation_b)

    def tearDown(self):
        for photo in (self.photo_a, self.photo_b):
            if photo.file:
                photo.file.delete(save=False)

    def _photo(self, gallery, name):
        photo = GalleryPhoto(
            gallery=gallery, photographer=self.studio, original_name=name,
            file_size=4, is_visible=True, status=GalleryPhoto.Status.COMPLETED,
        )
        photo.file.save(name, ContentFile(b"test"), save=False)
        photo.save()
        return photo

    def assert_hidden(self, response):
        self.assertEqual(response.status_code, 404)

    def test_token_a_cannot_retrieve_gallery_b_photo_media(self):
        response = self.client.get(reverse(
            "galleries:client_gallery_photo_media", args=[self.token_a, self.photo_b.pk]
        ))
        self.assert_hidden(response)

    def test_token_a_cannot_favorite_gallery_b_photo_or_create_event(self):
        before = GalleryAnalyticsEvent.objects.filter(gallery=self.gallery_b).count()
        response = self.client.post(reverse(
            "galleries:client_gallery_favorite", args=[self.token_a, self.photo_b.pk]
        ))
        self.assert_hidden(response)
        self.assertEqual(GalleryAnalyticsEvent.objects.filter(gallery=self.gallery_b).count(), before)

    def test_token_a_cannot_comment_on_gallery_b_photo(self):
        response = self.client.post(
            reverse("galleries:client_gallery_comment", args=[self.token_a, self.photo_b.pk]),
            {"comment": "cross-gallery write"},
        )
        self.assert_hidden(response)
        self.assertFalse(
            GalleryPhotoComment.objects.filter(photo=self.photo_b, body="cross-gallery write").exists()
        )

    def test_token_a_cannot_download_gallery_b_photo(self):
        response = self.client.get(reverse(
            "galleries:client_gallery_download", args=[self.token_a, self.photo_b.pk]
        ))
        self.assert_hidden(response)

    def test_token_a_cannot_download_gallery_b_original(self):
        response = self.client.get(reverse(
            "galleries:client_gallery_download_original", args=[self.token_a, self.photo_b.pk]
        ))
        self.assert_hidden(response)

    def test_token_a_gallery_page_does_not_leak_gallery_b_content(self):
        response = self.client.get(reverse("galleries:client_gallery_access", args=[self.token_a]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.photo_a.original_name)
        self.assertNotContains(response, self.photo_b.original_name)

    def test_favorites_are_isolated_per_bearer_token(self):
        self.client.post(reverse(
            "galleries:client_gallery_favorite", args=[self.token_a, self.photo_a.pk]
        ))
        self.assertTrue(GalleryAnalyticsEvent.objects.filter(
            gallery=self.gallery_a,
            visitor_identifier=self.token_a_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
            related_photo=self.photo_a,
        ).exists())
        self.assertFalse(GalleryAnalyticsEvent.objects.filter(
            visitor_identifier=self.token_b_record.token_hash,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
        ).exists())

    def test_comment_is_attributed_only_to_token_a_invitation(self):
        self.client.post(
            reverse("galleries:client_gallery_comment", args=[self.token_a, self.photo_a.pk]),
            {"comment": "A only"},
        )
        comment = GalleryPhotoComment.objects.get(photo=self.photo_a, body="A only")
        self.assertEqual(comment.gallery, self.gallery_a)
        self.assertEqual(comment.invitation, self.invitation_a)
        self.assertNotEqual(comment.invitation, self.invitation_b)

    def test_revoked_token_cannot_read_or_write(self):
        self.token_a_record.revoked_at = __import__("django").utils.timezone.now()
        self.token_a_record.save(update_fields=["revoked_at"])
        self.assert_hidden(self.client.get(reverse("galleries:client_gallery_access", args=[self.token_a])))
        self.assert_hidden(self.client.post(reverse(
            "galleries:client_gallery_favorite", args=[self.token_a, self.photo_a.pk]
        )))

    def test_expired_token_cannot_read_or_write(self):
        from django.utils import timezone
        self.token_a_record.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        self.token_a_record.save(update_fields=["expires_at"])
        self.assert_hidden(self.client.get(reverse("galleries:client_gallery_access", args=[self.token_a])))
        self.assert_hidden(self.client.post(
            reverse("galleries:client_gallery_comment", args=[self.token_a, self.photo_a.pk]),
            {"comment": "must not persist"},
        ))
        self.assertFalse(GalleryPhotoComment.objects.filter(body="must not persist").exists())
