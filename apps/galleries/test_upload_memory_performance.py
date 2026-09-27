import io

from django.core.files.uploadedfile import TemporaryUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from apps.dashboard.views import _validate_image_file


class UploadMemoryPerformanceTests(SimpleTestCase):
    def _jpeg_bytes(self):
        buffer = io.BytesIO()
        Image.new("RGB", (32, 32)).save(buffer, format="JPEG")
        return buffer.getvalue()

    def test_validation_accepts_seekable_stream_without_bytes_copy(self):
        payload = self._jpeg_bytes()
        stream = io.BytesIO(payload)
        self.assertTrue(_validate_image_file(stream, "image/jpeg", expected_size=len(payload)))

    def test_validation_rejects_size_mismatch_before_accepting_image(self):
        payload = self._jpeg_bytes()
        self.assertFalse(_validate_image_file(io.BytesIO(payload), "image/jpeg", expected_size=len(payload) + 1))

    def test_validation_supports_disk_backed_uploads(self):
        payload = self._jpeg_bytes()
        upload = TemporaryUploadedFile("photo.jpg", "image/jpeg", len(payload), None)
        try:
            upload.write(payload)
            upload.seek(0)
            self.assertTrue(_validate_image_file(upload, "image/jpeg", expected_size=len(payload)))
        finally:
            upload.close()
