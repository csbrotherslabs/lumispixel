from pathlib import Path

from django.test import SimpleTestCase


class TransactionSafetyContractTests(SimpleTestCase):
    def _source(self, relative_path):
        return (Path(__file__).resolve().parents[2] / relative_path).read_text(encoding="utf-8")

    def test_multipart_completion_locks_upload_state(self):
        source = self._source("apps/dashboard/views.py")
        self.assertIn(
            "GalleryMultipartUpload.objects.select_for_update().get(pk=session.pk)",
            source,
        )

    def test_favorite_toggle_serializes_on_gallery(self):
        source = self._source("apps/galleries/views.py")
        self.assertIn(
            "Gallery.objects.select_for_update().get(pk=gallery.pk)",
            source,
        )
