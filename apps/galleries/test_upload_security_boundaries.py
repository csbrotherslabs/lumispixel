"""Adversarial upload-security coverage."""
import io
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.dashboard.views import _validate_image_bytes
from apps.galleries.multipart_uploads import multipart_object_key


class UploadImageValidationTests(SimpleTestCase):
    def image_bytes(self, fmt="JPEG", size=(4, 4)):
        output = io.BytesIO()
        Image.new("RGB", size).save(output, format=fmt)
        return output.getvalue()

    def test_declared_mime_must_match_decoded_format(self):
        png = self.image_bytes("PNG")
        self.assertFalse(_validate_image_bytes(png, "image/jpeg"))
        self.assertTrue(_validate_image_bytes(png, "image/png"))

    def test_malformed_image_is_rejected(self):
        self.assertFalse(_validate_image_bytes(b"not-an-image", "image/jpeg"))

    @override_settings(MAX_GALLERY_IMAGE_PIXELS=100)
    def test_pixel_bomb_boundary_is_rejected(self):
        # Patch the module boundary because the limit is intentionally evaluated
        # without allocating a genuinely dangerous decompression-bomb fixture.
        with patch("apps.dashboard.views.MAX_IMAGE_PIXELS", 100):
            self.assertFalse(_validate_image_bytes(self.image_bytes(size=(11, 10)), "image/jpeg"))
            self.assertTrue(_validate_image_bytes(self.image_bytes(size=(10, 10)), "image/jpeg"))


class MultipartObjectKeySecurityTests(SimpleTestCase):
    @override_settings(GALLERY_STORAGE_ENVIRONMENT="prod")
    def test_client_filename_cannot_control_object_key(self):
        hostile = "../../other-gallery/evil.exe"
        key = multipart_object_key(
            photographer_id=12, gallery_id=34,
            original_name=hostile, content_type="image/jpeg",
        )
        self.assertTrue(key.startswith("private/prod/galleries/12/34/originals/"))
        self.assertTrue(key.endswith(".jpg"))
        self.assertNotIn("evil", key)
        self.assertNotIn("..", key)
        self.assertNotIn("\\", key)

    @override_settings(GALLERY_STORAGE_ENVIRONMENT="prod")
    def test_mime_controls_canonical_extension(self):
        cases = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        for mime, suffix in cases.items():
            with self.subTest(mime=mime):
                key = multipart_object_key(
                    photographer_id=1, gallery_id=2,
                    original_name="photo.anything", content_type=mime,
                )
                self.assertTrue(key.endswith(suffix))

    def test_unsupported_mime_cannot_create_object_key(self):
        with self.assertRaises(ValueError):
            multipart_object_key(
                photographer_id=1, gallery_id=2,
                original_name="payload.svg", content_type="image/svg+xml",
            )
