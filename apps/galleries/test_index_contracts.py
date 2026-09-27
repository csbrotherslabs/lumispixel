from django.test import SimpleTestCase

from apps.galleries.models import Gallery, GalleryMultipartUpload, GalleryPhoto


class GalleryIndexContractTests(SimpleTestCase):
    def assert_index(self, model, name, fields):
        indexes = {index.name: list(index.fields) for index in model._meta.indexes}
        self.assertEqual(indexes.get(name), fields)

    def test_active_gallery_workspace_index(self):
        self.assert_index(Gallery, "gallery_owner_active_date", ["photographer", "deleted_at", "archived_at", "-created_at"])

    def test_client_photo_delivery_index(self):
        self.assert_index(GalleryPhoto, "photo_gallery_visible_date", ["gallery", "status", "is_visible", "-created_at"])

    def test_stale_multipart_cleanup_index(self):
        self.assert_index(GalleryMultipartUpload, "multipart_active_created", ["completed_at", "aborted_at", "created_at"])

    def test_owner_gallery_multipart_index(self):
        self.assert_index(GalleryMultipartUpload, "multipart_owner_gallery", ["photographer", "gallery", "completed_at", "aborted_at"])
