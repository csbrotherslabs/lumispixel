import io

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
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
class ClientGalleryMobileBrowserTests(StaticLiveServerTestCase):
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

    def _assert_lightbox_contract(self, page, design):
        lightbox = page.locator("[data-photo-lightbox]")
        self.assertGreater(
            lightbox.count(),
            0,
            f"{design} rendered without the required [data-photo-lightbox] contract; url={page.url}",
        )
        return lightbox.first

    def _diagnostic_summary(self, page, design, console_messages, page_errors, requests, responses):
        script_sources = page.locator("script[src]").evaluate_all("els => els.map(e => e.src)")
        return (
            f"design={design}; url={page.url}; "
            f"readyState={page.evaluate('document.readyState')}; "
            f"lightboxes={page.locator('[data-photo-lightbox]').count()}; "
            f"full_view_controls={page.locator('[data-full-view]').count()}; "
            f"favorite_forms={page.locator('[data-favorite-form]').count()}; "
            f"scripts={script_sources}; "
            f"console={console_messages[-12:]}; page_errors={page_errors[-12:]}; "
            f"requests={requests[-20:]}; responses={responses[-20:]}"
        )

    def test_mobile_client_journey_across_all_gallery_designs(self):
        browser_results = []
        media_bytes = self._jpeg()
        for design, gallery_id, photo_id, invitation_id, token in self.gallery_cases:
            with self.subTest(design=design):
                context = self.browser.new_context(
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=3,
                    is_mobile=True,
                    has_touch=True,
                    accept_downloads=True,
                )
                # The browser contract must not depend on Cloudflare/B2 availability.
                # Keep signed delivery URLs in the rendered HTML, but fulfill those
                # image requests locally so failed external previews cannot change
                # layout/hit-testing and turn action clicks into media-link navigation.
                context.route(
                    "https://media-dev.lumispixel.com/**",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="image/jpeg",
                        body=media_bytes,
                    ),
                )
                try:
                    page = context.new_page()
                    response_failures = []
                    console_messages = []
                    page_errors = []
                    requests = []
                    responses = []
                    page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
                    page.on("pageerror", lambda error: page_errors.append(str(error)))
                    page.on("request", lambda request: requests.append(f"{request.method} {request.url}"))
                    page.on("response", lambda response: responses.append(f"{response.status} {response.url}"))
                    page.on(
                        "response",
                        lambda response: response_failures.append(f"{response.status} {response.url}")
                        if response.status >= 400
                        else None,
                    )
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

                    self._assert_lightbox_contract(page, design)
                    url_before_full_view = page.url
                    full_view = photo_card.locator("[data-full-view]")
                    full_view.scroll_into_view_if_needed()
                    full_view.click()
                    page.wait_for_timeout(150)
                    full_view_diag = self._diagnostic_summary(
                        page, design, console_messages, page_errors, requests, responses
                    )
                    self.assertEqual(
                        page.url,
                        url_before_full_view,
                        f"{design} full-view click unexpectedly navigated; {full_view_diag}",
                    )
                    self.assertTrue(
                        page.locator("[data-photo-lightbox]").first.evaluate("node => node.open"),
                        f"{design} full-view click did not open lightbox; {full_view_diag}",
                    )
                    page.locator("[data-photo-lightbox-close]").click()
                    self.assertFalse(page.locator("[data-photo-lightbox]").first.evaluate("node => node.open"))

                    url_before = page.url
                    favorite = photo_card.locator("[data-favorite-form] button")
                    favorite_url = photo_card.locator("[data-favorite-form]").get_attribute("action")
                    request_count_before = len(requests)
                    response_count_before = len(responses)
                    favorite.scroll_into_view_if_needed()
                    favorite.click()
                    try:
                        page.wait_for_function(
                            "(id) => document.querySelector(id)?.dataset.favorite === 'true'",
                            arg=f"#photo-{photo_id}",
                            timeout=5000,
                        )
                    except Exception as exc:
                        favorite_diag = self._diagnostic_summary(
                            page,
                            design,
                            console_messages,
                            page_errors,
                            requests[request_count_before:],
                            responses[response_count_before:],
                        )
                        self.fail(
                            f"{design} favorite did not transition after click; action={favorite_url}; "
                            f"error={exc}; {favorite_diag}"
                        )
                    self.assertEqual(page.url, url_before)
                    self.assertEqual(photo_card.locator("[data-favorite-count]").inner_text(), "1")

                    comment_toggle = photo_card.locator("[data-comment-toggle]")
                    comment_toggle.scroll_into_view_if_needed()
                    comment_toggle.click()
                    comment_form = photo_card.locator("[data-comment-form]")
                    self.assertTrue(comment_form.is_visible())
                    comment_form.locator('textarea[name="comment"]').fill(f"Looks great on {design}.")
                    comment_form.locator('button[type="submit"]').click()
                    page.wait_for_function(
                        "(id) => document.querySelector(id)?.querySelector('[data-comment-count]')?.textContent.trim() === '1'",
                        arg=f"#photo-{photo_id}",
                        timeout=5000,
                    )
                    self.assertEqual(page.url, url_before)

                    download_link = photo_card.locator('a[data-photo-download]').first
                    download_link.scroll_into_view_if_needed()
                    with page.expect_download() as download_info:
                        download_link.click()
                    self.assertTrue(download_info.value.suggested_filename)
                    self.assertEqual(photo_card.locator("[data-download-count]").first.inner_text(), "1")

                    if design == Gallery.DesignTemplate.KIMONO_STANDARD_FILTERABLE:
                        page.locator("[data-client-qr-open]").first.click()
                        share_dialog = page.locator("[data-client-qr-dialog]")
                        self.assertTrue(share_dialog.evaluate("node => node.open"))
                        self.assertTrue(share_dialog.locator("[data-client-copy-link]").is_visible())
                        page.locator("[data-client-qr-close]").click()
                    elif design in {
                        Gallery.DesignTemplate.KIMONO_STORY,
                        Gallery.DesignTemplate.KIMONO_MASONRY,
                    }:
                        page.locator("[data-qr-open]").first.click()
                        share_dialog = page.locator("[data-qr-dialog]")
                        self.assertTrue(share_dialog.evaluate("node => node.open"))
                        self.assertTrue(share_dialog.locator("[data-copy-link]").is_visible())
                        page.locator("[data-qr-close]").click()
                    else:
                        # Cinematic renders share launchers in both the stage QR panel
                        # and the photo browser. The stage is intentionally hidden once
                        # the browser opens, so exercise the control the client can see.
                        share_button = page.locator("[data-open-share]:visible").first
                        self.assertTrue(share_button.is_visible())
                        share_button.click()
                        share_dialog = page.locator("[data-share-dialog]")
                        self.assertTrue(share_dialog.evaluate("node => node.open"))
                        self.assertTrue(share_dialog.locator("[data-copy-link]").is_visible())
                        page.locator("[data-share-close]").click()

                    self.assertFalse(
                        response_failures,
                        f"{design} browser journey had failed HTTP responses: {response_failures}",
                    )
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
