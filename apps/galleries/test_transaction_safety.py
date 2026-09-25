import inspect

from django.test import SimpleTestCase

from apps.dashboard import views as dashboard_views
from apps.galleries import views as gallery_views


class TransactionSafetyContractTests(SimpleTestCase):
    def test_multipart_completion_locks_upload_state(self):
        self.assertIn(
            "GalleryMultipartUpload.objects.select_for_update().get(pk=session.pk)",
            inspect.getsource(dashboard_views.gallery_multipart_complete.__closure__[0].cell_contents),
        )

    def test_favorite_toggle_serializes_on_gallery(self):
        self.assertIn(
            "Gallery.objects.select_for_update().get(pk=gallery.pk)",
            inspect.getsource(gallery_views.client_gallery_favorite),
        )
