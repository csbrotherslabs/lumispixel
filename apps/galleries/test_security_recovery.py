import io
import json
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PhotographerProfile
from apps.galleries.models import Gallery, GalleryMultipartUpload, GalleryPhoto


def image_bytes(fmt="JPEG"):
    out = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(out, format=fmt)
    return out.getvalue()


@override_settings(
    GALLERY_STORAGE_BACKEND="local",
    GALLERY_STORAGE_ENVIRONMENT="dev",
    MAX_GALLERY_UPLOAD_BYTES=1024 * 1024,
)
class MultipartSecurityRecoveryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_user = User.objects.create_user(email="owner-security@example.com", password="test-pass-123")
        self.other_user = User.objects.create_user(email="other-security@example.com", password="test-pass-123")
        self.owner = PhotographerProfile.objects.create(user=self.owner_user)
        self.other = PhotographerProfile.objects.create(user=self.other_user)
        self.gallery = Gallery.objects.create(photographer=self.owner, name="Owner Gallery")
        self.other_gallery = Gallery.objects.create(photographer=self.other, name="Other Gallery")
        self.client = Client()
        self.client.force_login(self.owner_user)

    def post_json(self, url, data, client=None):
        return (client or self.client).post(url, data=json.dumps(data), content_type="application/json")

    def session(self, gallery=None, photographer=None):
        gallery = gallery or self.gallery
        photographer = photographer or self.owner
        return GalleryMultipartUpload.objects.create(
            gallery=gallery, photographer=photographer,
            object_key=f"private/dev/galleries/{photographer.pk}/{gallery.pk}/originals/security.jpg",
            upload_id=f"upload-{gallery.pk}", original_name="security.jpg",
            content_type="image/jpeg", file_size=len(image_bytes()),
        )

    def test_multipart_requires_authentication(self):
        anonymous = Client()
        response = anonymous.post(reverse("photographer_workspace:gallery_multipart_initiate"), data="{}", content_type="application/json")
        self.assertIn(response.status_code, (302, 401, 403))

    @patch("apps.dashboard.views.initiate_multipart", return_value="upload-1")
    def test_initiate_cannot_target_another_photographers_gallery(self, initiate):
        response = self.post_json(reverse("photographer_workspace:gallery_multipart_initiate"), {
            "gallery": self.other_gallery.pk, "name": "attack.jpg",
            "content_type": "image/jpeg", "size": 100,
        })
        self.assertEqual(response.status_code, 404)
        initiate.assert_not_called()

    def test_resume_sign_complete_and_abort_hide_foreign_upload_uuid(self):
        foreign = self.session(self.other_gallery, self.other)
        endpoints = [
            ("gallery_multipart_resume", {}),
            ("gallery_multipart_sign_part", {"part_number": 1}),
            ("gallery_multipart_complete", {"parts": [{"part_number": 1, "etag": "etag"}]}),
            ("gallery_multipart_abort", {}),
        ]
        for name, payload in endpoints:
            response = self.post_json(reverse(f"photographer_workspace:{name}", args=[foreign.pk]), payload)
            self.assertEqual(response.status_code, 404, name)

    @patch("apps.dashboard.views.sign_part", return_value="https://example.invalid/part")
    def test_part_number_validation_rejects_out_of_range_values(self, sign):
        upload = self.session()
        url = reverse("photographer_workspace:gallery_multipart_sign_part", args=[upload.pk])
        for number in (0, -1, 10001):
            self.assertEqual(self.post_json(url, {"part_number": number}).status_code, 400)
        sign.assert_not_called()

    @patch("apps.dashboard.views.complete_multipart")
    def test_completion_rejects_duplicate_or_out_of_order_parts_before_b2(self, complete):
        upload = self.session()
        url = reverse("photographer_workspace:gallery_multipart_complete", args=[upload.pk])
        bad = [
            [{"part_number": 2, "etag": "b"}, {"part_number": 1, "etag": "a"}],
            [{"part_number": 1, "etag": "a"}, {"part_number": 1, "etag": "b"}],
            [{"part_number": 2, "etag": "b"}],
        ]
        for parts in bad:
            self.assertEqual(self.post_json(url, {"parts": parts}).status_code, 400)
        complete.assert_not_called()

    @patch("apps.dashboard.views.delete_multipart_object")
    @patch("apps.dashboard.views.get_multipart_object_bytes", return_value=b"not-an-image")
    @patch("apps.dashboard.views.complete_multipart")
    def test_invalid_completed_object_is_deleted_and_session_released(self, complete, get_bytes, delete):
        upload = self.session()
        response = self.post_json(
            reverse("photographer_workspace:gallery_multipart_complete", args=[upload.pk]),
            {"parts": [{"part_number": 1, "etag": "etag"}]},
        )
        self.assertEqual(response.status_code, 400)
        upload.refresh_from_db()
        self.assertIsNotNone(upload.aborted_at)
        self.assertFalse(GalleryPhoto.objects.filter(gallery=self.gallery).exists())
        delete.assert_called_once_with(key=upload.object_key)

    @patch("apps.dashboard.views.list_multipart_parts", side_effect=RuntimeError("temporary B2 failure"))
    def test_resume_failure_does_not_mutate_upload_session(self, list_parts):
        upload = self.session()
        response = self.post_json(reverse("photographer_workspace:gallery_multipart_resume", args=[upload.pk]), {})
        self.assertEqual(response.status_code, 502)
        upload.refresh_from_db()
        self.assertIsNone(upload.completed_at)
        self.assertIsNone(upload.aborted_at)

    @patch("apps.dashboard.views.abort_multipart", side_effect=RuntimeError("temporary B2 failure"))
    def test_abort_failure_remains_active_for_later_recovery(self, abort):
        upload = self.session()
        response = self.post_json(reverse("photographer_workspace:gallery_multipart_abort", args=[upload.pk]), {})
        self.assertEqual(response.status_code, 502)
        upload.refresh_from_db()
        self.assertIsNone(upload.aborted_at)

    def test_csrf_is_enforced_on_multipart_mutations(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner_user)
        upload = self.session()
        response = csrf_client.post(
            reverse("photographer_workspace:gallery_multipart_abort", args=[upload.pk]),
            data="{}", content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class ProductionSecurityConfigurationTests(TestCase):
    def test_production_cookie_security_contract_is_declared(self):
        from django.conf import settings
        # CI normally runs DEBUG=True; these assertions protect the explicit
        # production branch in settings.py from accidental removal.
        settings_text = open(settings.BASE_DIR / "config" / "settings.py", encoding="utf-8").read()
        self.assertIn("SESSION_COOKIE_SECURE = True", settings_text)
        self.assertIn("CSRF_COOKIE_SECURE = True", settings_text)
        self.assertIn('MEDIA_SIGNING_SECRET is required for production signed media delivery.', settings_text)
        self.assertIn('Production requires GALLERY_STORAGE_BACKEND=b2.', settings_text)
