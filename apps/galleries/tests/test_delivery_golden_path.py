import io
import re
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.core import mail
from django.db import close_old_connections
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import (
    Gallery, GalleryAnalyticsEvent, GalleryInvitation, GalleryPhoto, GalleryPhotoComment,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    GALLERY_STORAGE_BACKEND="local",
)
class PhotographerClientDeliveryGoldenPathTests(LiveServerTestCase):
    """Browser-level smoke test for the revenue-critical gallery delivery lifecycle."""

    serialized_rollback = True

    def setUp(self):
        self.user = User.objects.create_user(email="golden-photographer@example.com", password="GoldenPath!123", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="golden-photographer", onboarding_completed=True)
        self.upload_bytes = self._jpeg()
        # Keep the browser/direct-upload workflow real while replacing only the
        # external object-storage provider boundary. The live Django server still
        # executes initiate/sign/complete, validation, persistence and accounting.
        self.storage_patchers = [
            patch("apps.dashboard.views.initiate_multipart", return_value="e2e-provider-upload"),
            patch("apps.dashboard.views.sign_part", return_value=self.live_server_url + "/__e2e-upload-part"),
            patch("apps.dashboard.views.complete_multipart", return_value=None),
            patch("apps.dashboard.views.get_multipart_object_stream", side_effect=lambda **_: io.BytesIO(self.upload_bytes)),
        ]
        for patcher in self.storage_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(accept_downloads=True)
        self.context.route("**/__e2e-upload-part", lambda route: route.fulfill(status=200, headers={"ETag": '"e2e-etag"'}, body=""))
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close(); self.browser.close(); self._playwright.stop()

    def _db(self, operation):
        def execute():
            close_old_connections()
            try: return operation()
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(execute).result()

    def _jpeg(self):
        buffer = io.BytesIO(); Image.new("RGB", (8, 8), (120, 80, 40)).save(buffer, format="JPEG"); return buffer.getvalue()

    def _login(self):
        self.page.goto(self.live_server_url + reverse("accounts:login"))
        login_email = self.page.locator("#id_email")
        login_form = login_email.locator("xpath=ancestor::form[1]")
        login_email.fill(self.user.email)
        login_form.locator('input[name="password"]').fill("GoldenPath!123")
        login_form.get_by_role("button", name=re.compile("sign in|log in", re.I)).click()
        self.page.wait_for_load_state("networkidle")

    def test_photographer_to_client_delivery_golden_path(self):
        self._login()
        self.page.goto(self.live_server_url + reverse("photographer_workspace:create_gallery"))
        self.page.locator('input[name="name"]').fill("Golden Delivery")
        self.page.locator('select[name="status"]').select_option("draft")
        self.page.locator('select[name="visibility"]').select_option("private")
        self.page.get_by_role("button", name="Create Gallery").click(); self.page.wait_for_load_state("networkidle")
        gallery_id = self._db(lambda: Gallery.objects.values_list("pk", flat=True).get(photographer_id=self.profile.pk, name="Golden Delivery"))
        self.assertIn(f"/galleries/{gallery_id}/", self.page.url)

        upload_url = self.live_server_url + reverse("photographer_workspace:gallery_upload_queue") + f"?gallery={gallery_id}"
        self.page.goto(upload_url); self.page.wait_for_load_state("networkidle")
        upload_input = self.page.locator("[data-upload-input]")
        upload_input.wait_for(state="attached")
        self.assertTrue(upload_input.is_enabled())
        upload_input.set_input_files({"name": "golden.jpg", "mimeType": "image/jpeg", "buffer": self.upload_bytes})
        completed_row = self.page.locator('[data-upload-list] [data-local-upload][data-status="completed"]')
        completed_row.wait_for(state="visible", timeout=30000)
        self.assertEqual(completed_row.locator(".lp-file-state strong").inner_text(), "Uploaded")
        photo_id = self._db(lambda: GalleryPhoto.objects.values_list("pk", flat=True).get(gallery_id=gallery_id, original_name="golden.jpg"))

        workspace_url = self.live_server_url + reverse("photographer_workspace:gallery_workspace", args=[gallery_id])
        self.page.goto(workspace_url)
        self.page.locator('form.lpw-gw-publish-form, form.lp-gw-publish-form').locator('button[type="submit"]').click(); self.page.wait_for_load_state("networkidle")
        self.assertEqual(self._db(lambda: Gallery.objects.values_list("status", flat=True).get(pk=gallery_id)), Gallery.Status.PUBLISHED)

        self.page.goto(workspace_url + "?tab=client-access")
        access_form = self.page.locator("#client-access-settings")
        access_form.locator('input[name="visibility"][value="private"]').check()
        for permission in ("view_gallery", "download_images", "favorite_photos", "comment"):
            checkbox = access_form.locator(f'input[name="{permission}"]')
            if not checkbox.is_checked(): checkbox.check()
        self.page.get_by_role("button", name="Save Access").click(); self.page.wait_for_load_state("networkidle")

        self.page.locator('#invite-client input[name="client_name"]').fill("Golden Client")
        self.page.locator('#invite-client input[name="email"]').fill("golden-client@example.com")
        self.page.locator('#invite-client button[type="submit"]').click(); self.page.wait_for_load_state("networkidle")
        self.assertTrue(mail.outbox)
        invitation_id = self._db(lambda: GalleryInvitation.objects.values_list("pk", flat=True).get(gallery_id=gallery_id, email="golden-client@example.com"))
        match = re.search(r"https?://[^\s]+/access/[^\s]+/", mail.outbox[-1].body); self.assertIsNotNone(match)
        client_url = match.group(0).replace("http://testserver", self.live_server_url).replace("https://testserver", self.live_server_url)

        client_context = self.browser.new_context(accept_downloads=True); client_page = client_context.new_page()
        client_page.goto(client_url); client_page.wait_for_load_state("networkidle"); self.assertIn("Golden Delivery", client_page.content())
        client_page.locator(f'form[action*="/photos/{photo_id}/favorite/"] button').first.click(); client_page.wait_for_timeout(250)
        comment_form = client_page.locator(f'form[action*="/photos/{photo_id}/comment/"]')
        comment_form.locator('textarea[name="comment"], input[name="comment"]').fill("This one is perfect."); comment_form.locator('button[type="submit"]').click(); client_page.wait_for_timeout(250)
        with client_page.expect_download() as download_info: client_page.locator(f'a[href*="/photos/{photo_id}/download/"]').first.click()
        self.assertTrue(download_info.value.suggested_filename); client_context.close()

        self.assertTrue(self._db(lambda: GalleryAnalyticsEvent.objects.filter(gallery_id=gallery_id, related_photo_id=photo_id, event_type=GalleryAnalyticsEvent.EventType.FAVORITE).exists()))
        self.assertTrue(self._db(lambda: GalleryPhotoComment.objects.filter(gallery_id=gallery_id, photo_id=photo_id, invitation_id=invitation_id, body="This one is perfect.").exists()))
        self.assertTrue(self._db(lambda: GalleryAnalyticsEvent.objects.filter(gallery_id=gallery_id, related_photo_id=photo_id, event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD).exists()))
        self.page.goto(workspace_url + "?tab=activity"); self.page.wait_for_load_state("networkidle")
        activity_text = self.page.locator("body").inner_text().lower(); self.assertIn("favorite", activity_text); self.assertIn("download", activity_text)
