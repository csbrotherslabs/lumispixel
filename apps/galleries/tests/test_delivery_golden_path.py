import io
import re
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.core import mail
from django.core.files.base import ContentFile
from django.db import close_old_connections, connections
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import (
    Gallery, GalleryAnalyticsEvent, GalleryInvitation, GalleryPhoto, GalleryPhotoComment,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    GALLERY_STORAGE_BACKEND="local",
    B2_MULTIPART_MIN_PART_BYTES=5 * 1024 * 1024,
    MEDIA_SIGNING_SECRET="p3-e2e-media-signing-secret-not-production",
)
class PhotographerClientDeliveryGoldenPathTests(LiveServerTestCase):
    """Browser-level smoke test for the revenue-critical gallery delivery lifecycle."""

    serialized_rollback = True

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
        self.upload_bytes = self._jpeg()
        self.storage_patchers = [
            patch("apps.dashboard.views.initiate_multipart", return_value="e2e-provider-upload"),
            patch("apps.dashboard.views.sign_part", return_value=self.live_server_url + "/__e2e-upload-part"),
            patch("apps.dashboard.views.complete_multipart", return_value=None),
            patch(
                "apps.dashboard.views.get_multipart_object_stream",
                side_effect=lambda **_: io.BytesIO(self.upload_bytes),
            ),
            patch("apps.dashboard.views.delete_multipart_object", return_value=None),
        ]
        for patcher in self.storage_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(accept_downloads=True)
        self.context.route(
            "**/__e2e-upload-part",
            lambda route: route.fulfill(
                status=200,
                headers={
                    "etag": '"e2e-etag"',
                    "access-control-expose-headers": "ETag",
                    "content-length": "0",
                },
                body="",
            ),
        )
        self.page = self.context.new_page()
        self.browser_errors = []
        self.page.on("pageerror", lambda exc: self.browser_errors.append(f"pageerror: {exc}"))
        self.page.on(
            "console",
            lambda msg: self.browser_errors.append(f"console {msg.type}: {msg.text}")
            if msg.type == "error" else None,
        )

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self._playwright.stop()

    def _db(self, operation):
        def execute():
            close_old_connections()
            try:
                return operation()
            finally:
                # Django's close_old_connections() deliberately leaves healthy
                # connections open. These short-lived executor threads must close
                # their own PostgreSQL sessions or LiveServerTestCase teardown can
                # be unable to drop the test database.
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(execute).result()

    def _jpeg(self):
        buffer = io.BytesIO()
        Image.effect_noise((2600, 2600), 100).convert("RGB").save(
            buffer, format="JPEG", quality=95
        )
        return buffer.getvalue()

    def _materialize_local_upload(self, photo_id):
        photo = GalleryPhoto.objects.get(pk=photo_id)
        storage = photo.file.storage
        name = photo.file.name
        if storage.exists(name):
            storage.delete(name)
        saved_name = storage.save(name, ContentFile(self.upload_bytes))
        if saved_name != name:
            storage.delete(saved_name)
            raise AssertionError(
                f"CI storage changed multipart object key from {name!r} to {saved_name!r}."
            )

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
        self.page.get_by_role("button", name="Create Gallery").click()
        self.page.wait_for_load_state("networkidle")
        gallery_id = self._db(
            lambda: Gallery.objects.values_list("pk", flat=True).get(
                photographer_id=self.profile.pk, name="Golden Delivery"
            )
        )
        self.assertIn(f"/galleries/{gallery_id}/", self.page.url)

        upload_url = self.live_server_url + reverse("photographer_workspace:gallery_upload_queue") + f"?gallery={gallery_id}"
        self.page.goto(upload_url)
        self.page.wait_for_load_state("networkidle")
        upload_input = self.page.locator("[data-upload-input]")
        upload_input.wait_for(state="attached")
        self.assertTrue(upload_input.is_enabled())
        upload_responses = []
        self.page.on(
            "response",
            lambda response: upload_responses.append(f"{response.status} {response.url}")
            if "/multipart/" in response.url or "__e2e-upload-part" in response.url else None,
        )
        upload_input.set_input_files({"name": "golden.jpg", "mimeType": "image/jpeg", "buffer": self.upload_bytes})
        terminal_row = self.page.locator(
            '[data-upload-list] [data-local-upload][data-status="completed"], '
            '[data-upload-list] [data-local-upload][data-status="failed"]'
        )
        try:
            terminal_row.wait_for(state="visible", timeout=15000)
        except Exception as exc:
            current_row = self.page.locator('[data-upload-list] [data-local-upload]').first
            row_status = current_row.get_attribute("data-status") if current_row.count() else "missing"
            row_text = current_row.inner_text() if current_row.count() else "no local upload row"
            self.fail(
                "Direct multipart upload never reached a terminal state. "
                f"row_status={row_status!r}; row={row_text!r}; responses={upload_responses!r}; "
                f"browser_errors={self.browser_errors!r}; playwright={exc}"
            )
        status = terminal_row.get_attribute("data-status")
        state_title = terminal_row.locator(".lp-file-state strong").inner_text()
        state_detail = terminal_row.locator(".lp-file-state span").inner_text()
        self.assertEqual(
            status, "completed",
            f"Direct multipart browser upload failed: {state_title}: {state_detail}; "
            f"responses={upload_responses!r}; browser_errors={self.browser_errors!r}",
        )
        self.assertEqual(state_title, "Uploaded")
        photo_id = self._db(
            lambda: GalleryPhoto.objects.values_list("pk", flat=True).get(
                gallery_id=gallery_id, original_name="golden.jpg"
            )
        )
        self._db(lambda: self._materialize_local_upload(photo_id))

        workspace_url = self.live_server_url + reverse("photographer_workspace:gallery_workspace", args=[gallery_id])
        self.page.goto(workspace_url)
        actions_menu = self.page.locator("details.lp-gw-actions-menu")
        actions_menu.locator("summary").click()
        publish_button = actions_menu.get_by_role("menuitem", name="Publish")
        expect(publish_button).to_be_visible()
        publish_button.click()
        self.page.wait_for_load_state("networkidle")
        self.assertEqual(
            self._db(lambda: Gallery.objects.values_list("status", flat=True).get(pk=gallery_id)),
            Gallery.Status.PUBLISHED,
        )

        self.page.goto(workspace_url + "?tab=client-access")
        access_form = self.page.locator("#client-access-settings")
        access_form.locator('input[name="visibility"][value="private"]').check()
        for permission in ("view_gallery", "download_images", "favorite_photos", "comment"):
            checkbox = access_form.locator(f'input[name="{permission}"]')
            if not checkbox.is_checked():
                checkbox.check()
        self.page.get_by_role("button", name="Save Access").click()
        self.page.wait_for_load_state("networkidle")

        self.page.locator('#invite-client input[name="client_name"]').fill("Golden Client")
        self.page.locator('#invite-client input[name="email"]').fill("golden-client@example.com")
        self.page.locator('#invite-client button[type="submit"]').click()
        self.page.wait_for_load_state("networkidle")
        self.assertTrue(mail.outbox)
        invitation_id = self._db(
            lambda: GalleryInvitation.objects.values_list("pk", flat=True).get(
                gallery_id=gallery_id, email="golden-client@example.com"
            )
        )
        match = re.search(r"https?://[^\s]+/access/[^\s]+/", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        client_url = match.group(0).replace("http://testserver", self.live_server_url).replace("https://testserver", self.live_server_url)

        client_context = self.browser.new_context(accept_downloads=True)
        client_page = client_context.new_page()
        client_page.goto(client_url)
        client_page.wait_for_load_state("networkidle")
        self.assertIn("Golden Delivery", client_page.content())
        client_page.locator(f'form[action*="/photos/{photo_id}/favorite/"] button').first.click()
        client_page.wait_for_timeout(250)

        photo = client_page.locator(f"#photo-{photo_id}")
        comment_toggle = photo.locator("[data-comment-toggle]")
        comment_panel = photo.locator("[data-comment-panel]")
        expect(comment_panel).to_be_hidden()
        comment_toggle.click()
        expect(comment_panel).to_be_visible()
        comment_form = comment_panel.locator("[data-comment-form]")
        comment_form.locator('textarea[name="comment"]').fill("This one is perfect.")
        comment_form.locator('button[type="submit"]').click()
        client_page.wait_for_timeout(250)

        with client_page.expect_download() as download_info:
            client_page.locator(f'a[href*="/photos/{photo_id}/download/"]').first.click()
        self.assertTrue(download_info.value.suggested_filename)
        client_context.close()

        self.assertTrue(self._db(lambda: GalleryAnalyticsEvent.objects.filter(
            gallery_id=gallery_id, related_photo_id=photo_id,
            event_type=GalleryAnalyticsEvent.EventType.FAVORITE,
        ).exists()))
        self.assertTrue(self._db(lambda: GalleryPhotoComment.objects.filter(
            gallery_id=gallery_id, photo_id=photo_id, invitation_id=invitation_id,
            body="This one is perfect.",
        ).exists()))
        self.assertTrue(self._db(lambda: GalleryAnalyticsEvent.objects.filter(
            gallery_id=gallery_id, related_photo_id=photo_id,
            event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD,
        ).exists()))
