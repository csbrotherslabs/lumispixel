import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import (
    AccessToken,
    Gallery,
    GalleryInvitation,
    GalleryPermission,
    GalleryPhoto,
    GallerySettings,
)


@override_settings(GALLERY_STORAGE_BACKEND="local")
class ClientPermissionBrowserMatrixTests(LiveServerTestCase):
    """Browser-visible controls and direct authorization must agree for client permissions."""

    serialized_rollback = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._playwright = sync_playwright().start()
        cls.browser = cls._playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._playwright.stop()
        super().tearDownClass()

    def setUp(self):
        user = User.objects.create_user(
            email="browser-matrix-owner@example.com",
            password="BrowserMatrix!123",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.owner = PhotographerProfile.objects.create(
            user=user,
            slug="browser-matrix-owner",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="Browser Permission Matrix",
            slug="browser-permission-matrix",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            design_template=Gallery.DesignTemplate.KIMONO_STANDARD_FILTERABLE,
        )
        self.permissions = GalleryPermission.objects.create(
            gallery=self.gallery,
            view_gallery=True,
            download_images=True,
            download_originals=True,
            favorite_photos=True,
            comment=True,
            share_gallery=True,
        )
        GallerySettings.objects.create(gallery=self.gallery, gallery_url=self.gallery.slug)
        image_bytes = self._jpeg()
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery,
            photographer=self.owner,
            file=SimpleUploadedFile("matrix.jpg", image_bytes, content_type="image/jpeg"),
            original_name="matrix.jpg",
            file_size=len(image_bytes),
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Matrix Client",
            email="matrix-client@example.com",
            status=GalleryInvitation.Status.PENDING,
        )
        _, self.raw_token = AccessToken.issue(self.invitation)
        self.gallery_path = reverse("galleries:client_gallery_access", args=[self.raw_token])
        self.favorite_path = reverse("galleries:client_gallery_favorite", args=[self.raw_token, self.photo.pk])
        self.comment_path = reverse("galleries:client_gallery_comment", args=[self.raw_token, self.photo.pk])
        self.download_path = reverse("galleries:client_gallery_download", args=[self.raw_token, self.photo.pk])
        self.original_path = reverse("galleries:client_gallery_download_original", args=[self.raw_token, self.photo.pk])
        self.zip_path = reverse("galleries:client_gallery_download_all", args=[self.raw_token])
        self.share_path = reverse("galleries:client_gallery_share", args=[self.raw_token])
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        if self.photo.file:
            self.photo.file.delete(save=False)

    def _jpeg(self):
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), (90, 120, 150)).save(buffer, format="JPEG")
        return buffer.getvalue()

    def _save_permission(self, field, value):
        setattr(self.permissions, field, value)
        self.permissions.save(update_fields=[field, "updated_at"])

    def _open_gallery(self):
        response = self.page.goto(self.live_server_url + self.gallery_path)
        self.page.wait_for_load_state("networkidle")
        return response

    def _api_status(self, method, path, data=None):
        url = self.live_server_url + path
        if method == "get":
            return self.context.request.get(url).status
        return self.context.request.post(url, form=data or {}).status

    def test_all_enabled_permissions_expose_client_controls(self):
        self._open_gallery()
        photo = self.page.locator(f"#photo-{self.photo.pk}")
        self.assertTrue(photo.locator("[data-favorite-form]").is_visible())
        self.assertTrue(photo.locator("[data-comment-toggle]").is_visible())
        self.assertTrue(photo.locator('a[href*="/download/"]').first.is_visible())
        self.assertTrue(photo.locator('a[href*="/download-original/"]').is_visible())
        self.assertTrue(self.page.get_by_text("Download Gallery", exact=False).first.is_visible())
        self.assertTrue(self.page.locator("[data-client-qr-open]").first.is_visible())

    def test_each_disabled_permission_hides_its_control_and_blocks_direct_endpoint(self):
        cases = (
            ("favorite_photos", "[data-favorite-form]", "post", self.favorite_path, {}),
            ("comment", "[data-comment-toggle]", "post", self.comment_path, {"comment": "blocked"}),
            ("share_gallery", "[data-client-qr-open]", "post", self.share_path, {}),
        )
        for field, selector, method, path, data in cases:
            with self.subTest(permission=field):
                self._save_permission(field, False)
                self._open_gallery()
                self.assertEqual(self.page.locator(selector).count(), 0)
                self.assertEqual(self._api_status(method, path, data), 403)
                self._save_permission(field, True)

    def test_download_images_off_hides_all_download_controls_and_blocks_endpoints(self):
        self._save_permission("download_images", False)
        self._open_gallery()
        self.assertEqual(self.page.locator("[data-photo-download]").count(), 0)
        self.assertEqual(self.page.get_by_text("Download Gallery", exact=False).count(), 0)
        self.assertEqual(self._api_status("get", self.download_path), 403)
        self.assertEqual(self._api_status("get", self.original_path), 403)
        self.assertEqual(self._api_status("get", self.zip_path), 403)

    def test_download_originals_off_only_hides_and_blocks_original_download(self):
        self._save_permission("download_originals", False)
        self._open_gallery()
        photo = self.page.locator(f"#photo-{self.photo.pk}")
        self.assertEqual(photo.locator('a[href*="/download-original/"]').count(), 0)
        self.assertTrue(photo.locator('a[href*="/download/"]').first.is_visible())
        self.assertEqual(self._api_status("get", self.original_path), 403)
        self.assertEqual(self._api_status("get", self.download_path), 200)

    def test_view_gallery_off_blocks_page_and_every_client_capability(self):
        self._save_permission("view_gallery", False)
        response = self._open_gallery()
        self.assertEqual(response.status, 404)
        checks = (
            ("get", self.download_path, None),
            ("get", self.original_path, None),
            ("get", self.zip_path, None),
            ("post", self.favorite_path, {}),
            ("post", self.comment_path, {"comment": "blocked"}),
            ("post", self.share_path, {}),
        )
        for method, path, data in checks:
            with self.subTest(path=path):
                self.assertEqual(self._api_status(method, path, data), 404)

    def test_download_expiration_hides_controls_and_blocks_direct_downloads(self):
        from django.utils import timezone

        self.permissions.download_expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.permissions.save(update_fields=["download_expires_at", "updated_at"])
        self._open_gallery()
        self.assertEqual(self.page.locator("[data-photo-download]").count(), 0)
        self.assertEqual(self.page.get_by_text("Download Gallery", exact=False).count(), 0)
        self.assertEqual(self._api_status("get", self.download_path), 403)
        self.assertEqual(self._api_status("get", self.original_path), 403)
        self.assertEqual(self._api_status("get", self.zip_path), 403)

    def test_revoked_token_blocks_page_and_direct_capabilities(self):
        from django.utils import timezone

        AccessToken.objects.filter(token_hash=AccessToken.digest(self.raw_token)).update(revoked_at=timezone.now())
        response = self._open_gallery()
        self.assertEqual(response.status, 404)
        for method, path, data in (
            ("get", self.download_path, None),
            ("get", self.original_path, None),
            ("get", self.zip_path, None),
            ("post", self.favorite_path, {}),
            ("post", self.comment_path, {"comment": "blocked"}),
            ("post", self.share_path, {}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self._api_status(method, path, data), 404)
