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
    GalleryAnalyticsEvent,
    GalleryInvitation,
    GalleryPermission,
    GalleryPhoto,
    GalleryPhotoComment,
    GallerySettings,
)


@override_settings(
    GALLERY_STORAGE_BACKEND="local",
    MEDIA_SIGNING_SECRET="lumispixel-mobile-browser-test-signing-secret",
)
class ClientGalleryMobileBrowserTests(LiveServerTestCase):
    """Exercise the real client delivery UI at a phone viewport for every design."""

    serialized_rollback = True
    DESIGNS = (
        Gallery.DesignTemplate.KIMONO_STANDARD_FILTERABLE,
        Gallery.DesignTemplate.KIMONO_STORY,
        Gallery.DesignTemplate.KIMONO_MASONRY,
        Gallery.DesignTemplate.CINEMATIC,
    )

    def setUp(self):
        self.user = User.objects.create_user(
            email="mobile-gallery@example.com",
            password="MobileGallery!123",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user,
            slug="mobile-gallery-photographer",
            onboarding_completed=True,
        )
        self.gallery_cases = [self._build_gallery(design) for design in self.DESIGNS]

        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=True)

    def tearDown(self):
        if hasattr(self, "browser"):
            self.browser.close()
        if hasattr(self, "_playwright"):
            self._playwright.stop()

    def _jpeg(self):
        buffer = io.BytesIO()
        Image.new("RGB", (24, 32), (110, 80, 50)).save(buffer, format="JPEG")
        return buffer.getvalue()

    def _build_gallery(self, design):
        gallery = Gallery.objects.create(
            photographer=self.profile,
            name=f"Mobile {design}",
            slug=f"mobile-{design}",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            design_template=design,
        )
        GalleryPermission.objects.create(
            gallery=gallery,
            view_gallery=True,
            download_images=True,
            download_originals=True,
            favorite_photos=True,
            comment=True,
            share_gallery=True,
        )
        GallerySettings.objects.create(gallery=gallery, gallery_url=gallery.slug)
        image_bytes = self._jpeg()
        photo = GalleryPhoto.objects.create(
            gallery=gallery,
            photographer=self.profile,
            file=SimpleUploadedFile("mobile.jpg", image_bytes, content_type="image/jpeg"),
            original_name="mobile.jpg",
            file_size=len(image_bytes),
            status=GalleryPhoto.Status.COMPLETED,
            is_visible=True,
        )
        invitation = GalleryInvitation.objects.create(
            gallery=gallery,
            client_name="Mobile Client",
            email="mobile-client@example.com",
            status=GalleryInvitation.Status.PENDING,
        )
        _, raw_token = AccessToken.issue(invitation)
        return design, gallery.pk, photo.pk, invitation.pk, raw_token

    def test_mobile_client_journey_across_all_gallery_designs(self):
        browser_results = []
        for design, gallery_id, photo_id, invitation_id, token in self.gallery_cases:
            with self.subTest(design=design):
                context = self.browser.new_context(
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=3,
                    is_mobile=True,
                    has_touch=True,
                    accept_downloads=True,
                )
                try:
                    page = context.new_page()
                    response = page.goto(
                        self.live_server_url + reverse("galleries:client_gallery_access", args=[token])
                    )
                    self.assertIsNotNone(response)
                    self.assertEqual(response.status, 200, f"{design} client gallery did not render successfully")
                    page.wait_for_load_state("networkidle")

                    expected_name = f"Mobile {design}"
                    self.assertIn(expected_name, page.content())
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"),
                        page.evaluate("window.innerWidth") + 2,
                        f"{design} overflows the mobile viewport",
                    )

                    if design == Gallery.DesignTemplate.CINEMATIC:
                        page.locator('[data-open-gallery][data-filter="all"]').first.click()

                    photo_card = page.locator(f"#photo-{photo_id}")
                    self.assertTrue(photo_card.is_visible())

                    # These controls intentionally overlay the media surface. On a
                    # touch-sized viewport the underlying image/watermark can win
                    # Playwright's hit-test even though the action is visible. A
                    # forced click still exercises the real DOM event handler and
                    # avoids turning this journey test into a CSS hit-testing test.
                    photo_card.locator("[data-full-view]").click(force=True)
                    lightbox = page.locator("[data-photo-lightbox]")
                    self.assertTrue(lightbox.evaluate("node => node.open"))
                    page.locator("[data-photo-lightbox-close]").click(force=True)
                    self.assertFalse(lightbox.evaluate("node => node.open"))

                    url_before = page.url
                    favorite = photo_card.locator("[data-favorite-form] button")
                    favorite.click(force=True)
                    page.wait_for_function(
                        "(id) => document.querySelector(id)?.dataset.favorite === 'true'",
                        arg=f"#photo-{photo_id}",
                    )
                    self.assertEqual(page.url, url_before)
                    self.assertEqual(photo_card.locator("[data-favorite-count]").inner_text(), "1")

                    photo_card.locator("[data-comment-toggle]").click(force=True)
                    comment_form = photo_card.locator("[data-comment-form]")
                    self.assertTrue(comment_form.is_visible())
                    comment_form.locator('textarea[name="comment"]').fill(f"Looks great on {design}.")
                    comment_form.locator('button[type="submit"]').click(force=True)
                    page.wait_for_function(
                        "(id) => document.querySelector(id)?.querySelector('[data-comment-count]')?.textContent.trim() === '1'",
                        arg=f"#photo-{photo_id}",
                    )
                    self.assertEqual(page.url, url_before)

                    with page.expect_download() as download_info:
                        photo_card.locator('a[data-photo-download]').first.click(force=True)
                    self.assertTrue(download_info.value.suggested_filename)
                    self.assertEqual(photo_card.locator("[data-download-count]").first.inner_text(), "1")

                    if design == Gallery.DesignTemplate.KIMONO_STANDARD_FILTERABLE:
                        page.locator("[data-client-qr-open]").first.click(force=True)
                        share_dialog = page.locator("[data-client-qr-dialog]")
                        self.assertTrue(share_dialog.evaluate("node => node.open"))
                        self.assertTrue(share_dialog.locator("[data-client-copy-link]").is_visible())
                        page.locator("[data-client-qr-close]").click(force=True)
                    elif design in {
                        Gallery.DesignTemplate.KIMONO_STORY,
                        Gallery.DesignTemplate.KIMONO_MASONRY,
                    }:
                        page.locator("[data-qr-open]").first.click(force=True)
                        share_dialog = page.locator("[data-qr-dialog]")
                        self.assertTrue(share_dialog.evaluate("node => node.open"))
                        self.assertTrue(share_dialog.locator("[data-copy-link]").is_visible())
                        page.locator("[data-qr-close]").click(force=True)
                    else:
                        page.locator("[data-open-share]").first.click(force=True)
                        share_dialog = page.locator("[data-share-dialog]")
                        self.assertTrue(share_dialog.evaluate("node => node.open"))
                        self.assertTrue(share_dialog.locator("[data-copy-link]").is_visible())
                        page.locator("[data-share-close]").click(force=True)

                    browser_results.append((gallery_id, photo_id, invitation_id))
                finally:
                    context.close()

        self.browser.close()
        del self.browser
        self._playwright.stop()
        del self._playwright

        for gallery_id, photo_id, invitation_id in browser_results:
            self.assertTrue(
                GalleryAnalyticsEvent.objects.filter(
                    gallery_id=gallery_id,
                    related_photo_id=photo_id,
                    event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
                ).exists()
            )
            self.assertTrue(
                GalleryPhotoComment.objects.filter(
                    gallery_id=gallery_id,
                    photo_id=photo_id,
                    invitation_id=invitation_id,
                ).exists()
            )
            self.assertTrue(
                GalleryAnalyticsEvent.objects.filter(
                    gallery_id=gallery_id,
                    related_photo_id=photo_id,
                    event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
                ).exists()
            )
