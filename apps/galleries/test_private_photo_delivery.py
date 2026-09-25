"""Private-photo delivery security boundaries."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.media_delivery import _media_path, signed_media_url
from apps.galleries.models import AccessToken, Gallery, GalleryInvitation, GalleryPermission, GalleryPhoto


@override_settings(
    MEDIA_SIGNING_SECRET="private-photo-delivery-test-secret-32chars",
    MEDIA_DELIVERY_BASE_URL="https://media.example.test",
)
class PrivatePhotoDeliveryTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="private-media-owner@example.com", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.studio = PhotographerProfile.objects.create(
            user=owner, slug="private-media", onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.studio, name="Private", slug="private",
            status=Gallery.Status.PUBLISHED,
        )
        self.permissions = GalleryPermission.objects.create(
            gallery=self.gallery, view_gallery=True, download_images=True,
            download_originals=True, automatic_gallery_lock=True,
        )
        self.photo = GalleryPhoto(
            gallery=self.gallery, photographer=self.studio, original_name="secret.jpg",
            file_size=6, is_visible=True, status=GalleryPhoto.Status.COMPLETED,
        )
        self.photo.file.save("secret.jpg", ContentFile(b"secret"), save=False)
        self.photo.save()
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Client", email="client@example.com",
        )
        self.token_record, self.token = AccessToken.issue(self.invitation)

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def media_url(self):
        return reverse("galleries:client_gallery_photo_media", args=[self.token, self.photo.pk])

    def original_url(self):
        return reverse("galleries:client_gallery_download_original", args=[self.token, self.photo.pk])

    def test_preview_requires_valid_gallery_token(self):
        self.assertEqual(self.client.get(self.media_url()).status_code, 200)
        bad = reverse("galleries:client_gallery_photo_media", args=["invalid-token", self.photo.pk])
        self.assertEqual(self.client.get(bad).status_code, 404)

    def test_original_requires_explicit_original_permission(self):
        self.permissions.download_originals = False
        self.permissions.save(update_fields=["download_originals"])
        self.assertEqual(self.client.get(self.original_url()).status_code, 403)

    def test_original_requires_general_download_permission_too(self):
        self.permissions.download_images = False
        self.permissions.save(update_fields=["download_images"])
        self.assertEqual(self.client.get(self.original_url()).status_code, 403)

    def test_hidden_photo_cannot_be_retrieved_by_predictable_id(self):
        self.photo.is_visible = False
        self.photo.save(update_fields=["is_visible"])
        self.assertEqual(self.client.get(self.media_url()).status_code, 404)
        self.assertEqual(self.client.get(self.original_url()).status_code, 404)

    def test_archived_gallery_blocks_preview_and_original(self):
        self.gallery.archived_at = timezone.now()
        self.gallery.save(update_fields=["archived_at"])
        self.assertEqual(self.client.get(self.media_url()).status_code, 404)
        self.assertEqual(self.client.get(self.original_url()).status_code, 404)

    def test_revoked_token_blocks_preview_and_original(self):
        self.token_record.revoked_at = timezone.now()
        self.token_record.save(update_fields=["revoked_at"])
        self.assertEqual(self.client.get(self.media_url()).status_code, 404)
        self.assertEqual(self.client.get(self.original_url()).status_code, 404)

    def test_expired_token_blocks_preview_and_original(self):
        self.token_record.expires_at = timezone.now() - timedelta(seconds=1)
        self.token_record.save(update_fields=["expires_at"])
        self.assertEqual(self.client.get(self.media_url()).status_code, 404)
        self.assertEqual(self.client.get(self.original_url()).status_code, 404)

    def test_locked_expired_gallery_blocks_preview_and_original(self):
        self.gallery.expires_at = timezone.now() - timedelta(seconds=1)
        self.gallery.save(update_fields=["expires_at"])
        self.assertEqual(self.client.get(self.media_url()).status_code, 404)
        self.assertEqual(self.client.get(self.original_url()).status_code, 404)

    def test_direct_media_url_does_not_map_private_gallery_storage_in_debug(self):
        # Private originals live under PRIVATE_MEDIA_ROOT, while Django's DEBUG
        # /media/ helper serves MEDIA_ROOT only.
        with TemporaryDirectory() as public_root, TemporaryDirectory() as private_root:
            public_root = Path(public_root)
            private_root = Path(private_root)
            private_file = private_root / "galleries" / "secret.jpg"
            private_file.parent.mkdir(parents=True)
            private_file.write_bytes(b"secret")
            with override_settings(MEDIA_ROOT=public_root, PRIVATE_MEDIA_ROOT=private_root):
                response = self.client.get("/media/galleries/secret.jpg")
            self.assertEqual(response.status_code, 404)

    def test_cloudflare_url_is_short_lived_and_signed(self):
        url = signed_media_url(self.photo.file.name, ttl=60, now=1_000)
        self.assertTrue(url.startswith("https://media.example.test/private/dev/"))
        self.assertIn("expires=1060", url)
        self.assertIn("signature=", url)
        self.assertNotIn("secret.jpg?", url.split("/private/dev/", 1)[0])

    def test_b2_storage_contract_is_private_and_authenticated(self):
        from apps.galleries.storage import PrivateGalleryObjectStorage
        self.assertEqual(PrivateGalleryObjectStorage.default_acl, "private")
        self.assertTrue(PrivateGalleryObjectStorage.querystring_auth)

    def test_media_path_encodes_path_segments(self):
        path = _media_path(self.photo.file.name)
        self.assertTrue(path.startswith("/private/dev/"))
        self.assertNotIn("\\", path)
