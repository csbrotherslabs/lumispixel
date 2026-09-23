from decimal import Decimal

from django.core.exceptions import ValidationError
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client

from .analytics import gallery_analytics_report, track_gallery_event
from .forms import GallerySettingsForm
from .models import AccessToken, Album, AlbumPhoto, Gallery, GalleryAnalyticsEvent, GalleryInvitation, GalleryOrder, GalleryPermission, GalleryPhoto, GalleryPhotoComment, GallerySettings, GalleryStore, StoreProduct
from .storage import PrivateGalleryB2Storage, gallery_photo_storage

# Client gallery templates render signed Cloudflare media URLs. Keep unit tests
# self-contained instead of depending on a CI/production signing secret.
TEST_MEDIA_DELIVERY_SETTINGS = {
    "MEDIA_DELIVERY_BASE_URL": "https://media-dev.lumispixel.test",
    "MEDIA_SIGNING_SECRET": "test-media-signing-secret",
    "MEDIA_SIGNED_URL_TTL": 900,
}


class GalleryStorageTests(SimpleTestCase):
    @override_settings(
        GALLERY_STORAGE_BACKEND="b2",
        GALLERY_STORAGE_ENVIRONMENT="prod",
        B2_ACCESS_KEY_ID="test-key-id",
        B2_SECRET_ACCESS_KEY="test-secret",
        B2_BUCKET_NAME="lumispixel-production-media",
        B2_REGION="us-west-004",
        B2_ENDPOINT_URL="https://s3.us-west-004.backblazeb2.com",
        B2_SIGNED_URL_TTL=900,
    )
    def test_b2_backend_is_private_and_bucket_scoped(self):
        storage = gallery_photo_storage()

        self.assertIsInstance(storage, PrivateGalleryB2Storage)
        self.assertEqual(storage.bucket_name, "lumispixel-production-media")
        self.assertEqual(storage.endpoint_url, "https://s3.us-west-004.backblazeb2.com")
        self.assertEqual(storage.location, "private/prod")
        self.assertTrue(storage.querystring_auth)
        self.assertFalse(storage.file_overwrite)

    @override_settings(
        GALLERY_STORAGE_BACKEND="b2",
        GALLERY_STORAGE_ENVIRONMENT="prod",
        B2_ACCESS_KEY_ID="test-key-id",
        B2_SECRET_ACCESS_KEY="test-secret",
        B2_BUCKET_NAME="lumispixel-production-media",
        B2_REGION="us-west-004",
        B2_ENDPOINT_URL="https://s3.us-west-004.backblazeb2.com",
        B2_SIGNED_URL_TTL=900,
    )
    def test_b2_backend_preserves_originals_namespace(self):
        storage = gallery_photo_storage()

        generated = storage.generate_filename("galleries/12/34/IMG_0001.jpg")

        self.assertEqual(generated, "galleries/12/34/originals/IMG_0001.jpg")

    @override_settings(GALLERY_STORAGE_BACKEND="local")
    def test_local_backend_remains_available_for_development_and_ci(self):
        storage = gallery_photo_storage()

        self.assertEqual(storage.location, str(settings.PRIVATE_MEDIA_ROOT))




class GalleryModelTests(TestCase):
    def test_analytics_tracking_and_reports_are_owner_scoped(self):
        user = User.objects.create_user(email="analytics@example.com", password="testpass")
        other_user = User.objects.create_user(email="other-analytics@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="analytics-owner")
        other = PhotographerProfile.objects.create(user=other_user, slug="other-analytics-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Wedding", slug="analytics-wedding")
        other_gallery = Gallery.objects.create(photographer=other, name="Other", slug="analytics-other")

        track_gallery_event(gallery=gallery, event_type="view", visitor_identifier="opaque-1", session_identifier="session-1", device_category="mobile")
        track_gallery_event(gallery=gallery, event_type="favorite", visitor_identifier="opaque-1", session_identifier="session-1")
        track_gallery_event(gallery=other_gallery, event_type="view", visitor_identifier="opaque-2")
        report = gallery_analytics_report(gallery=gallery)

        self.assertEqual(report["counts"]["views"], 1)
        self.assertEqual(report["counts"]["favorites"], 1)
        self.assertEqual(report["counts"]["visitors"], 1)
        self.assertEqual(GalleryAnalyticsEvent.objects.for_photographer(owner).count(), 2)

    def test_analytics_purchase_revenue_is_aggregated_as_decimal(self):
        user = User.objects.create_user(email="analytics-revenue@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="analytics-revenue-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Revenue", slug="analytics-revenue")

        track_gallery_event(
            gallery=gallery,
            event_type=GalleryAnalyticsEvent.EventType.PURCHASE,
            visitor_identifier="opaque-revenue",
            session_identifier="session-revenue",
            metadata={"revenue": "42.50"},
        )

        report = gallery_analytics_report(gallery=gallery)

        self.assertEqual(report["counts"]["revenue"], Decimal("42.50"))
        self.assertEqual(report["store"]["revenue"], Decimal("42.50"))

    def test_analytics_event_rejects_cross_gallery_photo(self):
        user = User.objects.create_user(email="analytics-photo@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="analytics-photo-owner")
        gallery = Gallery.objects.create(photographer=owner, name="First", slug="analytics-first")
        other_gallery = Gallery.objects.create(photographer=owner, name="Second", slug="analytics-second")
        photo = GalleryPhoto.objects.create(gallery=other_gallery, photographer=owner, file="other.jpg", original_name="other.jpg")

        with self.assertRaises(ValidationError):
            track_gallery_event(gallery=gallery, event_type="photo_view", photo=photo)

    def test_gallery_defaults_and_owner_scoping(self):
        user = User.objects.create_user(email="owner@example.com", password="testpass", primary_role=User.PrimaryRole.PHOTOGRAPHER)
        other_user = User.objects.create_user(email="other@example.com", password="testpass", primary_role=User.PrimaryRole.PHOTOGRAPHER)
        owner = PhotographerProfile.objects.create(user=user, slug="owner")
        other = PhotographerProfile.objects.create(user=other_user, slug="other")
        gallery = Gallery.objects.create(photographer=owner, name="Wedding", slug="wedding")
        Gallery.objects.create(photographer=other, name="Portrait", slug="portrait")

        self.assertEqual(gallery.status, Gallery.Status.DRAFT)
        self.assertEqual(gallery.visibility, Gallery.Visibility.PRIVATE)
        self.assertEqual(list(Gallery.objects.for_photographer(owner)), [gallery])

    def test_client_must_belong_to_gallery_photographer(self):
        owner_user = User.objects.create_user(email="one@example.com", password="testpass")
        other_user = User.objects.create_user(email="two@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=owner_user, slug="one")
        other = PhotographerProfile.objects.create(user=other_user, slug="two")
        client = Client.objects.create(photographer=other, first_name="Wrong owner")

        gallery = Gallery(photographer=owner, client=client, name="Invalid", slug="invalid")
        with self.assertRaises(ValidationError):
            gallery.full_clean()

    def test_album_curates_only_photos_from_its_gallery(self):
        user = User.objects.create_user(email="albums@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="album-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Wedding", slug="wedding")
        other_gallery = Gallery.objects.create(photographer=owner, name="Portraits", slug="portraits")
        photo = GalleryPhoto.objects.create(gallery=other_gallery, photographer=owner, file="other.jpg", original_name="other.jpg")
        album = Album.objects.create(gallery=gallery, name="Ceremony", visibility=Album.Visibility.CLIENT_ONLY)

        membership = AlbumPhoto(album=album, photo=photo)
        with self.assertRaises(ValidationError):
            membership.full_clean()

        self.assertEqual(list(Album.objects.for_photographer(owner)), [album])

    def test_store_product_and_order_enforce_owner_boundaries(self):
        first_user = User.objects.create_user(email="store@example.com", password="testpass")
        second_user = User.objects.create_user(email="other-store@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=first_user, slug="store-owner")
        other = PhotographerProfile.objects.create(user=second_user, slug="other-store-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Store Gallery", slug="store-gallery")
        store = GalleryStore.objects.create(photographer=owner, gallery=gallery, name="Keepsakes")

        product = StoreProduct(store=store, gallery=gallery, photographer=other, name="Print", product_type=StoreProduct.ProductType.PRINT, price="25.00")
        with self.assertRaises(ValidationError):
            product.full_clean()
        order = GalleryOrder(store=store, gallery=gallery, photographer=other, order_number="LP-100", customer_name="Client", customer_email="client@example.com")
        with self.assertRaises(ValidationError):
            order.full_clean()

    def test_sale_price_must_be_lower_than_regular_price(self):
        user = User.objects.create_user(email="pricing@example.com", password="testpass")
        owner = PhotographerProfile.objects.create(user=user, slug="pricing-owner")
        gallery = Gallery.objects.create(photographer=owner, name="Pricing", slug="pricing")
        store = GalleryStore.objects.create(photographer=owner, gallery=gallery)
        product = StoreProduct(store=store, gallery=gallery, photographer=owner, name="Download", product_type=StoreProduct.ProductType.DIGITAL, price="10.00", sale_price="10.00")
        with self.assertRaises(ValidationError):
            product.full_clean()


@override_settings(GALLERY_STORAGE_BACKEND="local", **TEST_MEDIA_DELIVERY_SETTINGS)
class ClientDownloadPermissionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="download-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="download-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Download Test",
            slug="download-test",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery, download_images=True)
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug, allow_downloads=False)
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Client", email="client@example.com"
        )
        _, self.raw_token = AccessToken.issue(self.invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("photo.jpg", b"client-download-test", content_type="image/jpeg"),
            original_name="photo.jpg",
            file_size=20,
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def test_download_permission_controls_client_ui_without_gallery_settings_duplicate(self):
        response = self.client.get(reverse("galleries:client_gallery_access", args=[self.raw_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Download Gallery")
        self.assertContains(response, reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk]))

        self.permissions.download_images = False
        self.permissions.save(update_fields=["download_images", "updated_at"])
        response = self.client.get(reverse("galleries:client_gallery_access", args=[self.raw_token]))
        self.assertNotContains(response, "Download Gallery")
        self.assertNotContains(response, reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk]))

    def test_disabled_download_permission_blocks_direct_photo_and_gallery_endpoints(self):
        self.permissions.download_images = False
        self.permissions.save(update_fields=["download_images", "updated_at"])
        photo_response = self.client.get(reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk]))
        gallery_response = self.client.get(reverse("galleries:client_gallery_download_all", args=[self.raw_token]))
        self.assertEqual(photo_response.status_code, 403)
        self.assertEqual(gallery_response.status_code, 403)

    def test_expired_download_permission_hides_ui_and_blocks_endpoints(self):
        self.permissions.download_expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.permissions.save(update_fields=["download_expires_at", "updated_at"])
        page = self.client.get(reverse("galleries:client_gallery_access", args=[self.raw_token]))
        self.assertNotContains(page, "Download Gallery")
        self.assertEqual(self.client.get(reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("galleries:client_gallery_download_all", args=[self.raw_token])).status_code, 403)

    def test_gallery_download_returns_zip_and_records_downloads(self):
        response = self.client.get(reverse("galleries:client_gallery_download_all", args=[self.raw_token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                visitor_identifier=AccessToken.digest(self.raw_token),
                event_type=GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD,
            ).count(),
            1,
        )
        self.assertEqual(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                visitor_identifier=AccessToken.digest(self.raw_token),
                event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
            ).count(),
            1,
        )


@override_settings(GALLERY_STORAGE_BACKEND="local", **TEST_MEDIA_DELIVERY_SETTINGS)
class ClientOriginalDownloadPermissionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="original-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="original-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Original Test",
            slug="original-test",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(
            gallery=self.gallery,
            download_images=True,
            download_originals=False,
        )
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug)
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Client", email="original-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("original.jpg", b"original-file-bytes", content_type="image/jpeg"),
            original_name="original.jpg",
            file_size=19,
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )
        self.original_url = reverse(
            "galleries:client_gallery_download_original",
            args=[self.raw_token, self.photo.pk],
        )

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def test_original_download_is_hidden_and_forbidden_when_permission_is_off(self):
        page = self.client.get(reverse("galleries:client_gallery_access", args=[self.raw_token]))
        self.assertNotContains(page, self.original_url)
        self.assertEqual(self.client.get(self.original_url).status_code, 403)

    def test_original_download_is_visible_and_allowed_when_both_download_permissions_are_on(self):
        self.permissions.download_originals = True
        self.permissions.save(update_fields=["download_originals", "updated_at"])
        page = self.client.get(reverse("galleries:client_gallery_access", args=[self.raw_token]))
        self.assertContains(page, self.original_url)
        response = self.client.get(self.original_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_original_permission_cannot_bypass_download_images_permission(self):
        self.permissions.download_images = False
        self.permissions.download_originals = True
        self.permissions.save(update_fields=["download_images", "download_originals", "updated_at"])
        page = self.client.get(reverse("galleries:client_gallery_access", args=[self.raw_token]))
        self.assertNotContains(page, self.original_url)
        self.assertEqual(self.client.get(self.original_url).status_code, 403)

    def test_original_download_respects_expiration_and_download_limit(self):
        self.permissions.download_originals = True
        self.permissions.download_expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.permissions.save(update_fields=["download_originals", "download_expires_at", "updated_at"])
        self.assertEqual(self.client.get(self.original_url).status_code, 403)

        self.permissions.download_expires_at = None
        self.permissions.save(update_fields=["download_expires_at", "updated_at"])
        settings = GallerySettings.objects.get(gallery=self.gallery)
        settings.download_limit = 0
        settings.save(update_fields=["download_limit", "updated_at"])
        self.assertEqual(self.client.get(self.original_url).status_code, 403)

    def test_original_download_is_recorded_as_an_original_download(self):
        self.permissions.download_originals = True
        self.permissions.save(update_fields=["download_originals", "updated_at"])
        self.assertEqual(self.client.get(self.original_url).status_code, 200)
        event = GalleryAnalyticsEvent.objects.filter(
            gallery=self.gallery,
            visitor_identifier=AccessToken.digest(self.raw_token),
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
            related_photo=self.photo,
        ).latest("occurred_at")
        self.assertEqual(event.source, "original_download")
        self.assertTrue(event.metadata.get("original"))


@override_settings(GALLERY_STORAGE_BACKEND="local", **TEST_MEDIA_DELIVERY_SETTINGS)
class ClientFavoritePermissionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="favorite-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="favorite-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Favorite Test",
            slug="favorite-test",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery, favorite_photos=True)
        # Deliberately false: Client Permissions is the authorization source of truth.
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug, enable_favorites=False)
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Client", email="favorite-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("favorite.jpg", b"favorite-file", content_type="image/jpeg"),
            original_name="favorite.jpg",
            file_size=13,
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )
        self.gallery_url = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.favorite_url = reverse("galleries:client_gallery_favorite", args=[self.raw_token, self.photo.pk])

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def test_client_permission_controls_favorite_ui_without_duplicate_gallery_setting(self):
        page = self.client.get(self.gallery_url)
        self.assertContains(page, self.favorite_url)
        self.permissions.favorite_photos = False
        self.permissions.save(update_fields=["favorite_photos", "updated_at"])
        page = self.client.get(self.gallery_url)
        self.assertNotContains(page, self.favorite_url)

    def test_disabled_favorite_permission_blocks_direct_endpoint(self):
        self.permissions.favorite_photos = False
        self.permissions.save(update_fields=["favorite_photos", "updated_at"])
        self.assertEqual(self.client.post(self.favorite_url).status_code, 403)

    def test_favorite_can_be_added_and_removed_and_count_stays_consistent(self):
        first = self.client.post(self.favorite_url)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, "Favorite saved")
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.favorite_count, 1)
        self.assertEqual(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                visitor_identifier=AccessToken.digest(self.raw_token),
                event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
                related_photo=self.photo,
            ).count(),
            1,
        )

        page = self.client.get(self.gallery_url)
        self.assertContains(page, "Remove Favorite")

        second = self.client.post(self.favorite_url)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, "Favorite removed")
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.favorite_count, 0)
        self.assertFalse(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                visitor_identifier=AccessToken.digest(self.raw_token),
                event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
                related_photo=self.photo,
            ).exists()
        )

        page = self.client.get(self.gallery_url)
        self.assertContains(page, "Favorite")
        self.assertNotContains(page, "Remove Favorite")

    def test_duplicate_favorite_posts_do_not_inflate_gallery_count(self):
        self.client.post(self.favorite_url)
        self.client.post(self.favorite_url)
        self.client.post(self.favorite_url)
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.favorite_count, 1)


@override_settings(GALLERY_STORAGE_BACKEND="local", **TEST_MEDIA_DELIVERY_SETTINGS)
class ClientCommentPermissionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="comment-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="comment-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner, name="Comment Test", slug="comment-test",
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery, comment=True)
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug, enable_comments=False)
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Comment Client", email="comment-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(self.invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=self.owner,
            file=SimpleUploadedFile("comment.jpg", b"comment-file", content_type="image/jpeg"),
            original_name="comment.jpg", file_size=12,
            status=GalleryPhoto.Status.COMPLETED, is_visible=True,
        )
        self.gallery_url = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.comment_url = reverse("galleries:client_gallery_comment", args=[self.raw_token, self.photo.pk])

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def test_comment_permission_controls_ui_without_duplicate_gallery_setting(self):
        self.assertContains(self.client.get(self.gallery_url), self.comment_url)
        self.permissions.comment = False
        self.permissions.save(update_fields=["comment", "updated_at"])
        self.assertNotContains(self.client.get(self.gallery_url), self.comment_url)

    def test_disabled_comment_permission_blocks_direct_endpoint(self):
        self.permissions.comment = False
        self.permissions.save(update_fields=["comment", "updated_at"])
        self.assertEqual(self.client.post(self.comment_url, {"comment": "Please retouch this."}).status_code, 403)

    def test_client_can_post_and_view_photo_comment(self):
        response = self.client.post(self.comment_url, {"comment": "Please retouch this photo."})
        self.assertEqual(response.status_code, 302)
        comment = GalleryPhotoComment.objects.get(gallery=self.gallery, photo=self.photo)
        self.assertEqual(comment.body, "Please retouch this photo.")
        self.assertEqual(comment.invitation, self.invitation)
        page = self.client.get(self.gallery_url)
        self.assertContains(page, "Please retouch this photo.")
        self.assertContains(page, "Comment Client")

    def test_blank_comment_is_not_created(self):
        self.client.post(self.comment_url, {"comment": "   "})
        self.assertFalse(GalleryPhotoComment.objects.filter(gallery=self.gallery).exists())

    def test_comment_records_analytics(self):
        self.client.post(self.comment_url, {"comment": "Love this one."})
        self.assertTrue(
            GalleryAnalyticsEvent.objects.filter(
                gallery=self.gallery,
                visitor_identifier=AccessToken.digest(self.raw_token),
                event_type=GalleryAnalyticsEvent.EventType.COMMENT,
                related_photo=self.photo,
            ).exists()
        )


@override_settings(GALLERY_STORAGE_BACKEND="local")
class ClientSharePermissionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="share-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="share-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner, name="Share Test", slug="share-test",
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery, share_gallery=True)
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug)
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Share Client", email="share-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(invitation)
        self.gallery_url = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.share_url = reverse("galleries:client_gallery_share", args=[self.raw_token])
        self.stable_path = reverse("galleries:stable_gallery_access", args=[self.gallery.public_id])

    def test_share_permission_controls_link_and_qr_ui(self):
        page = self.client.get(self.gallery_url)
        self.assertContains(page, self.stable_path)
        self.assertContains(page, "Copy Link")
        self.assertContains(page, "Download QR")
        self.assertTemplateUsed(page, "galleries/designs/standard_filterable.html")

        self.permissions.share_gallery = False
        self.permissions.save(update_fields=["share_gallery", "updated_at"])
        page = self.client.get(self.gallery_url)
        self.assertNotContains(page, "Copy Link")
        self.assertNotContains(page, "Download QR")
        self.assertNotContains(page, self.share_url)

    def test_disabled_share_permission_blocks_direct_share_endpoint(self):
        self.permissions.share_gallery = False
        self.permissions.save(update_fields=["share_gallery", "updated_at"])
        self.assertEqual(self.client.post(self.share_url).status_code, 403)

    def test_share_records_analytics_and_uses_stable_gallery_url(self):
        response = self.client.post(self.share_url)
        self.assertEqual(response.status_code, 302)
        event = GalleryAnalyticsEvent.objects.filter(
            gallery=self.gallery,
            visitor_identifier=AccessToken.digest(self.raw_token),
            event_type=GalleryAnalyticsEvent.EventType.SHARE,
        ).latest("occurred_at")
        self.assertIn(self.stable_path, event.metadata["shared_url"])
        self.assertNotIn(self.raw_token, event.metadata["shared_url"])

    def test_stable_share_url_preserves_private_gallery_access_rules(self):
        response = self.client.get(self.stable_path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "galleries/stable_gallery_gate.html")


@override_settings(GALLERY_STORAGE_BACKEND="local")
class ClientPurchasePrintsPermissionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="prints-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="prints-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner, name="Print Test", slug="print-test",
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(gallery=self.gallery, purchase_prints=True)
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug)
        self.store = GalleryStore.objects.create(
            gallery=self.gallery, photographer=self.owner, enabled=True, name="Print Shop"
        )
        self.product = StoreProduct.objects.create(
            store=self.store, photographer=self.owner, gallery=self.gallery,
            name="8x10 Print", product_type=StoreProduct.ProductType.PRINT,
            price="25.00", fulfillment=StoreProduct.Fulfillment.PHYSICAL, active=True,
        )
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Print Client", email="print-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(invitation)
        self.gallery_url = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.store_url = reverse("galleries:client_gallery_print_store", args=[self.raw_token])

    def test_purchase_prints_on_exposes_active_store(self):
        page = self.client.get(self.gallery_url)
        self.assertContains(page, "Shop Prints")
        self.assertContains(page, self.store_url)
        store_page = self.client.get(self.store_url)
        self.assertEqual(store_page.status_code, 200)
        self.assertContains(store_page, "8x10 Print")

    def test_purchase_prints_off_hides_store_and_blocks_direct_access(self):
        self.permissions.purchase_prints = False
        self.permissions.save(update_fields=["purchase_prints", "updated_at"])
        self.assertNotContains(self.client.get(self.gallery_url), "Shop Prints")
        self.assertEqual(self.client.get(self.store_url).status_code, 403)

    def test_disabled_or_expired_store_is_not_exposed(self):
        self.store.enabled = False
        self.store.save(update_fields=["enabled", "updated_at"])
        self.assertNotContains(self.client.get(self.gallery_url), "Shop Prints")
        self.assertEqual(self.client.get(self.store_url).status_code, 404)

        self.store.enabled = True
        self.store.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.store.save(update_fields=["enabled", "expires_at", "updated_at"])
        self.assertNotContains(self.client.get(self.gallery_url), "Shop Prints")
        self.assertEqual(self.client.get(self.store_url).status_code, 404)

    def test_non_print_products_do_not_enable_print_store(self):
        self.product.product_type = StoreProduct.ProductType.DIGITAL
        self.product.save(update_fields=["product_type", "updated_at"])
        self.assertNotContains(self.client.get(self.gallery_url), "Shop Prints")
        self.assertEqual(self.client.get(self.store_url).status_code, 404)


class GallerySettingsPermissionSeparationTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="settings-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="settings-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner, name="Settings Test", slug="settings-test"
        )
        self.settings = GallerySettings.objects.create(
            gallery=self.gallery, gallery_url=self.gallery.slug,
            allow_downloads=False, allow_original_downloads=False,
            enable_favorites=False, enable_comments=False,
        )

    def test_gallery_settings_form_does_not_expose_client_authorization_fields(self):
        form = GallerySettingsForm(instance=self.settings, photographer=self.owner)
        for field_name in (
            "allow_downloads",
            "allow_original_downloads",
            "enable_favorites",
            "enable_comments",
        ):
            self.assertNotIn(field_name, form.fields)
        self.assertIn("zip_downloads", form.fields)
        self.assertIn("download_limit", form.fields)

    def test_posting_legacy_permission_fields_cannot_change_them_through_settings_form(self):
        form = GallerySettingsForm(
            data={
                "gallery_url": self.gallery.slug,
                "accent_color": self.settings.accent_color,
                "theme": self.settings.theme,
                "watermark_position": self.settings.watermark_position,
                "zip_downloads": self.settings.zip_downloads,
                "download_limit": "",
                "allow_downloads": "on",
                "allow_original_downloads": "on",
                "enable_favorites": "on",
                "enable_comments": "on",
            },
            instance=self.settings,
            photographer=self.owner,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertFalse(saved.allow_downloads)
        self.assertFalse(saved.allow_original_downloads)
        self.assertFalse(saved.enable_favorites)
        self.assertFalse(saved.enable_comments)


@override_settings(GALLERY_STORAGE_BACKEND="local", **TEST_MEDIA_DELIVERY_SETTINGS)
class ClientAdvancedAccessRuleTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="advanced-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="advanced-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner, name="Advanced Rules", slug="advanced-rules",
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(
            gallery=self.gallery, download_images=True,
            automatic_gallery_lock=False, watermark=GalleryPermission.Watermark.PREVIEW,
        )
        self.settings = GallerySettings.objects.create(
            gallery=self.gallery, gallery_url=self.gallery.slug,
            watermark_position=GallerySettings.WatermarkPosition.BOTTOM_RIGHT,
        )
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Advanced Client", email="advanced-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(invitation)
        self.gallery_url = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.stable_url = reverse("galleries:stable_gallery_access", args=[self.gallery.public_id])
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=self.owner,
            file=SimpleUploadedFile("advanced.jpg", b"advanced-file", content_type="image/jpeg"),
            original_name="advanced.jpg", file_size=13,
            status=GalleryPhoto.Status.COMPLETED, is_visible=True,
        )
        self.download_url = reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk])

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def test_download_expiration_hides_downloads_and_blocks_direct_endpoint(self):
        self.permissions.download_expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.permissions.save(update_fields=["download_expires_at", "updated_at"])
        page = self.client.get(self.gallery_url)
        self.assertNotContains(page, self.download_url)
        self.assertEqual(self.client.get(self.download_url).status_code, 403)

    def test_gallery_expiration_only_locks_access_when_automatic_lock_is_enabled(self):
        # Keep the database invariant expires_at > published_at while making
        # the gallery expired relative to now.
        self.gallery.published_at = timezone.now() - timezone.timedelta(days=2)
        self.gallery.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.gallery.save(update_fields=["published_at", "expires_at", "updated_at"])
        self.assertEqual(self.client.get(self.gallery_url).status_code, 200)
        self.permissions.automatic_gallery_lock = True
        self.permissions.save(update_fields=["automatic_gallery_lock", "updated_at"])
        self.assertEqual(self.client.get(self.gallery_url).status_code, 404)
        self.assertEqual(self.client.get(self.stable_url).status_code, 404)

    def test_preview_watermark_is_rendered_at_configured_position(self):
        page = self.client.get(self.gallery_url)
        self.assertContains(page, "lp-client-photo__watermark")
        self.assertContains(page, "is-watermark-bottom_right")

    def test_none_watermark_removes_preview_overlay(self):
        self.permissions.watermark = GalleryPermission.Watermark.NONE
        self.permissions.save(update_fields=["watermark", "updated_at"])
        page = self.client.get(self.gallery_url)
        self.assertNotContains(page, 'class="lp-client-photo__watermark"')


@override_settings(GALLERY_STORAGE_BACKEND="local", **TEST_MEDIA_DELIVERY_SETTINGS)
class ClientPermissionMatrixTests(TestCase):
    """Cross-permission regression tests: UI hiding must match endpoint authorization."""

    def setUp(self):
        user = User.objects.create_user(email="matrix-owner@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="matrix-owner")
        self.gallery = Gallery.objects.create(
            photographer=self.owner, name="Permission Matrix", slug="permission-matrix",
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.permissions = GalleryPermission.objects.create(
            gallery=self.gallery,
            view_gallery=True, download_images=True, download_originals=True,
            favorite_photos=True, comment=True, share_gallery=True, purchase_prints=True,
        )
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug)
        self.store = GalleryStore.objects.create(
            gallery=self.gallery, photographer=self.owner, enabled=True, name="Matrix Store"
        )
        StoreProduct.objects.create(
            store=self.store, photographer=self.owner, gallery=self.gallery,
            name="Matrix Print", product_type=StoreProduct.ProductType.PRINT,
            price="20.00", fulfillment=StoreProduct.Fulfillment.PHYSICAL, active=True,
        )
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="Matrix Client", email="matrix-client@example.com"
        )
        _, self.raw_token = AccessToken.issue(self.invitation)
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=self.owner,
            file=SimpleUploadedFile("matrix.jpg", b"matrix-file", content_type="image/jpeg"),
            original_name="matrix.jpg", file_size=11,
            status=GalleryPhoto.Status.COMPLETED, is_visible=True,
        )
        self.gallery_url = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.favorite_url = reverse("galleries:client_gallery_favorite", args=[self.raw_token, self.photo.pk])
        self.comment_url = reverse("galleries:client_gallery_comment", args=[self.raw_token, self.photo.pk])
        self.download_url = reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk])
        self.original_url = reverse("galleries:client_gallery_download_original", args=[self.raw_token, self.photo.pk])
        self.zip_url = reverse("galleries:client_gallery_download_all", args=[self.raw_token])
        self.share_url = reverse("galleries:client_gallery_share", args=[self.raw_token])
        self.print_url = reverse("galleries:client_gallery_print_store", args=[self.raw_token])

    def tearDown(self):
        if self.photo.file:
            self.photo.file.delete(save=False)

    def test_view_gallery_off_blocks_every_token_protected_capability(self):
        self.permissions.view_gallery = False
        self.permissions.save(update_fields=["view_gallery", "updated_at"])
        self.assertEqual(self.client.get(self.gallery_url).status_code, 404)
        checks = (
            ("get", self.download_url, None),
            ("get", self.original_url, None),
            ("get", self.zip_url, None),
            ("post", self.favorite_url, {}),
            ("post", self.comment_url, {"comment": "blocked"}),
            ("post", self.share_url, {}),
            ("get", self.print_url, None),
        )
        for method, url, data in checks:
            response = getattr(self.client, method)(url, data or {})
            self.assertEqual(response.status_code, 404, url)

    def test_each_disabled_permission_blocks_its_direct_endpoint_without_disabling_others(self):
        cases = (
            ("download_images", "get", self.download_url),
            ("favorite_photos", "post", self.favorite_url),
            ("comment", "post", self.comment_url),
            ("share_gallery", "post", self.share_url),
            ("purchase_prints", "get", self.print_url),
        )
        for field, method, url in cases:
            setattr(self.permissions, field, False)
            self.permissions.save(update_fields=[field, "updated_at"])
            response = getattr(self.client, method)(url, {"comment": "test"} if field == "comment" else {})
            self.assertEqual(response.status_code, 403, field)
            setattr(self.permissions, field, True)
            self.permissions.save(update_fields=[field, "updated_at"])
            self.assertEqual(self.client.get(self.gallery_url).status_code, 200, field)

    def test_download_images_off_also_blocks_original_and_gallery_zip(self):
        self.permissions.download_images = False
        self.permissions.download_originals = True
        self.permissions.save(update_fields=["download_images", "download_originals", "updated_at"])
        self.assertEqual(self.client.get(self.download_url).status_code, 403)
        self.assertEqual(self.client.get(self.original_url).status_code, 403)
        self.assertEqual(self.client.get(self.zip_url).status_code, 403)

    def test_expired_or_revoked_token_blocks_all_capabilities(self):
        token_hash = AccessToken.digest(self.raw_token)
        AccessToken.objects.filter(token_hash=token_hash).update(revoked_at=timezone.now())
        for method, url in (
            ("get", self.gallery_url), ("get", self.download_url), ("get", self.original_url),
            ("get", self.zip_url), ("post", self.favorite_url), ("post", self.comment_url),
            ("post", self.share_url), ("get", self.print_url),
        ):
            response = getattr(self.client, method)(url, {"comment": "blocked"} if url == self.comment_url else {})
            self.assertEqual(response.status_code, 404, url)

    def test_hidden_or_incomplete_photo_cannot_be_acted_on(self):
        self.photo.is_visible = False
        self.photo.save(update_fields=["is_visible"])
        for method, url in (
            ("get", self.download_url), ("get", self.original_url),
            ("post", self.favorite_url), ("post", self.comment_url),
        ):
            response = getattr(self.client, method)(url, {"comment": "blocked"} if url == self.comment_url else {})
            self.assertEqual(response.status_code, 404, url)

    def test_all_permissions_on_exposes_expected_client_controls(self):
        page = self.client.get(self.gallery_url)
        for expected in ("Download Gallery", "Download Original", "Favorite", "Comment", "Copy Link", "Shop Prints"):
            self.assertContains(page, expected)
