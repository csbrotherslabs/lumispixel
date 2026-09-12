from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User

from .models import (
    AccessToken,
    Gallery,
    GalleryActivity,
    GalleryAnalyticsEvent,
    GalleryInvitation,
    GalleryPermission,
    GalleryPhoto,
    GallerySettings,
)


class ClientGalleryDeliveryTests(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user(
            email="delivery-owner@example.com",
            password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.owner = PhotographerProfile.objects.create(
            user=self.owner_user,
            slug="delivery-owner",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Client Delivery",
            slug="client-delivery",
            status=Gallery.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery)
        self.settings = GallerySettings.objects.create(
            gallery=self.gallery,
            gallery_url="client-delivery",
        )
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Avery Stone",
            email="avery@example.com",
        )
        self.token_record, self.raw_token = AccessToken.issue(self.invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("client-photo.jpg", b"client-photo-bytes", content_type="image/jpeg"),
            original_name="client-photo.jpg",
            file_size=18,
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )

    def access_url(self):
        return reverse("galleries:client_gallery_access", args=[self.raw_token])

    def test_invited_client_can_open_published_gallery(self):
        response = self.client.get(self.access_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "galleries/client_gallery.html")
        self.assertEqual(response.context["gallery"], self.gallery)
        self.assertEqual(list(response.context["photos"]), [self.photo])
        self.invitation.refresh_from_db()
        self.token_record.refresh_from_db()
        self.assertEqual(self.invitation.status, GalleryInvitation.Status.ACTIVE)
        self.assertIsNotNone(self.invitation.last_access_at)
        self.assertIsNotNone(self.token_record.last_used_at)
        self.assertTrue(GalleryAnalyticsEvent.objects.filter(gallery=self.gallery, event_type="view").exists())
        self.assertTrue(GalleryActivity.objects.filter(gallery=self.gallery, event_type="client_viewed").exists())

    def test_revoked_expired_and_unpublished_access_is_rejected(self):
        self.token_record.revoked_at = timezone.now()
        self.token_record.save(update_fields=["revoked_at"])
        self.assertEqual(self.client.get(self.access_url()).status_code, 404)

        self.token_record.revoked_at = None
        self.token_record.save(update_fields=["revoked_at"])
        self.gallery.status = Gallery.Status.READY
        self.gallery.save(update_fields=["status"])
        self.assertEqual(self.client.get(self.access_url()).status_code, 404)

    def test_favorite_is_permission_aware_and_idempotent(self):
        url = reverse("galleries:client_gallery_favorite", args=[self.raw_token, self.photo.pk])
        first = self.client.post(url)
        second = self.client.post(url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                related_photo=self.photo,
                event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
            ).count(),
            1,
        )
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.favorite_count, 1)

        self.permissions.favorite_photos = False
        self.permissions.save(update_fields=["favorite_photos"])
        other = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("other.jpg", b"other", content_type="image/jpeg"),
            original_name="other.jpg",
            status=GalleryPhoto.Status.COMPLETED,
        )
        blocked = self.client.post(reverse("galleries:client_gallery_favorite", args=[self.raw_token, other.pk]))
        self.assertEqual(blocked.status_code, 403)

    def test_download_requires_permission_and_records_delivery(self):
        url = reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()

        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.download_count, 1)
        self.assertTrue(GalleryAnalyticsEvent.objects.filter(
            gallery=self.gallery,
            related_photo=self.photo,
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
        ).exists())

        self.permissions.download_images = False
        self.permissions.save(update_fields=["download_images"])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_photo_media_is_scoped_to_token_gallery(self):
        other_gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Other",
            slug="other-delivery",
            status=Gallery.Status.PUBLISHED,
        )
        other_photo = GalleryPhoto.objects.create(
            gallery=other_gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("private.jpg", b"private", content_type="image/jpeg"),
            original_name="private.jpg",
            status=GalleryPhoto.Status.COMPLETED,
        )
        url = reverse("galleries:client_gallery_photo_media", args=[self.raw_token, other_photo.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_photographer_can_generate_copyable_share_link_for_invitation(self):
        self.client.force_login(self.owner_user)
        old_token = self.token_record
        url = reverse(
            "galleries:issue_client_gallery_share_link",
            args=[self.gallery.pk, self.invitation.pk],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "galleries/share_link_ready.html")
        share_url = response.context["share_url"]
        self.assertIn("/galleries/access/", share_url)
        old_token.refresh_from_db()
        self.assertIsNotNone(old_token.revoked_at)
        self.assertTrue(GalleryActivity.objects.filter(
            gallery=self.gallery,
            event_type=GalleryActivity.EventType.GALLERY_SHARED,
        ).exists())
