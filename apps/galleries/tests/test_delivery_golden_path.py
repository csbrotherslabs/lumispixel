import io
import re
import threading

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import (
    Gallery, GalleryAnalyticsEvent, GalleryInvitation, GalleryPhotoComment,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    GALLERY_STORAGE_BACKEND="local",
)
class PhotographerClientDeliveryGoldenPathTests(LiveServerTestCase):
    """Browser-level smoke test for the revenue-critical gallery delivery lifecycle."""

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
        self.user = User.objects.create_user(
            email="golden-photographer@example.com",
            password="GoldenPath!123",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user,
            slug="golden-photographer",
            onboarding_completed=True,
        )
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def _jpeg(self):
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), (120, 80, 40)).save(buffer, format="JPEG")
        return buffer.getvalue()

    def _login(self):
        self.page.goto(self.live_server_url + reverse("accounts:login"))
        self.page.locator('input[name="email"]').fill(self.user.email)
        self.page.locator('input[name="password"]').fill("GoldenPath!123")
        self.page.get_by_role("button", name=re.compile("sign in|log in", re.I)).click()
        self.page.wait_for_load_state("networkidle")

    def test_photographer_to_client_delivery_golden_path(self):
        self._login()

        # Photographer creates a gallery through the real rendered form.
        self.page.goto(self.live_server_url + reverse("photographer_workspace:create_gallery"))
        self.page.locator('input[name="name"]').fill("Golden Delivery")
        self.page.locator('select[name="status"]').select_option("draft")
        self.page.locator('select[name="visibility"]').select_option("private")
        self.page.get_by_role("button", name="Create Gallery").click()
        self.page.wait_for_load_state("networkidle")
        gallery = Gallery.objects.get(photographer=self.profile, name="Golden Delivery")
        self.assertIn(f"/galleries/{gallery.pk}/", self.page.url)

        # Upload a real JPEG through the fallback browser form/API surface.
        upload_url = self.live_server_url + reverse("photographer_workspace:gallery_upload_queue")
        response = self.page.request.post(
            upload_url,
            multipart={
                "gallery": str(gallery.pk),
                "files": {
                    "name": "golden.jpg",
                    "mimeType": "image/jpeg",
                    "buffer": self._jpeg(),
                },
            },
        )
        self.assertEqual(response.status, 201)
        photo_id = response.json()["uploads"][0]["id"]

        # Publish and enable the client interactions exercised below.
        workspace_url = self.live_server_url + reverse(
            "photographer_workspace:gallery_workspace", args=[gallery.pk]
        )
        self.page.goto(workspace_url)
        self.page.locator('form.lpw-gw-publish-form, form.lp-gw-publish-form').locator('button[type="submit"]').click()
        self.page.wait_for_load_state("networkidle")
        gallery.refresh_from_db()
        self.assertEqual(gallery.status, Gallery.Status.PUBLISHED)

        self.page.goto(workspace_url + "?tab=client-access")
        access_form = self.page.locator("#client-access-settings")
        access_form.locator('input[name="visibility"][value="private"]').check()
        for permission in ("view_gallery", "download_images", "favorite_photos", "comment"):
            checkbox = access_form.locator(f'input[name="{permission}"]')
            if not checkbox.is_checked():
                checkbox.check()
        self.page.get_by_role("button", name="Save Access").click()
        self.page.wait_for_load_state("networkidle")

        # Send the invitation through the browser and extract the secure URL from locmem email.
        self.page.locator('#invite-client input[name="client_name"]').fill("Golden Client")
        self.page.locator('#invite-client input[name="email"]').fill("golden-client@example.com")
        self.page.locator('#invite-client button[type="submit"]').click()
        self.page.wait_for_load_state("networkidle")
        self.assertTrue(mail.outbox)
        invitation = GalleryInvitation.objects.get(gallery=gallery, email="golden-client@example.com")
        match = re.search(r"https?://[^\s]+/access/[^\s]+/", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        client_url = match.group(0).replace("http://testserver", self.live_server_url).replace(
            "https://testserver", self.live_server_url
        )

        # Client opens the secure delivery, favorites, comments, and downloads without page refresh.
        client_context = self.browser.new_context(accept_downloads=True)
        client_page = client_context.new_page()
        client_page.goto(client_url)
        client_page.wait_for_load_state("networkidle")
        self.assertIn("Golden Delivery", client_page.content())

        favorite = client_page.locator(f'form[action*="/photos/{photo_id}/favorite/"] button').first
        favorite.click()
        client_page.wait_for_timeout(250)

        comment_form = client_page.locator(f'form[action*="/photos/{photo_id}/comment/"]')
        comment_form.locator('textarea[name="comment"], input[name="comment"]').fill("This one is perfect.")
        comment_form.locator('button[type="submit"]').click()
        client_page.wait_for_timeout(250)

        download_link = client_page.locator(f'a[href*="/photos/{photo_id}/download/"]').first
        with client_page.expect_download() as download_info:
            download_link.click()
        self.assertTrue(download_info.value.suggested_filename)
        client_context.close()

        self.assertTrue(GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            related_photo_id=photo_id,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
        ).exists())
        self.assertTrue(GalleryPhotoComment.objects.filter(
            gallery=gallery,
            photo_id=photo_id,
            invitation=invitation,
            body="This one is perfect.",
        ).exists())
        self.assertTrue(GalleryAnalyticsEvent.objects.filter(
            gallery=gallery,
            related_photo_id=photo_id,
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
        ).exists())

        # Photographer can see the resulting engagement back in the workspace.
        self.page.goto(workspace_url + "?tab=activity")
        self.page.wait_for_load_state("networkidle")
        activity_text = self.page.locator("body").inner_text().lower()
        self.assertIn("favorite", activity_text)
        self.assertIn("download", activity_text)
