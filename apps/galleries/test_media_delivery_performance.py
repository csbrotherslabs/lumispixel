from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, override_settings

from apps.galleries.media_delivery import signed_media_url
from apps.galleries.models import GalleryPhoto


@override_settings(
    MEDIA_DELIVERY_BASE_URL="https://media.example.test",
    MEDIA_SIGNING_SECRET="thumbnail-delivery-test-secret",
    MEDIA_SIGNED_URL_TTL=900,
    GALLERY_STORAGE_ENVIRONMENT="dev",
)
class GalleryMediaDeliveryPerformanceTests(SimpleTestCase):
    def _photo(self):
        photo = GalleryPhoto(original_name="photo.jpg", file_size=100)
        photo.file.name = "galleries/1/2/originals/photo.jpg"
        return photo

    def test_gallery_delivery_url_requests_preview_variant(self):
        query = parse_qs(urlparse(self._photo().delivery_url).query)
        self.assertEqual(query["variant"], ["preview"])

    def test_thumbnail_url_requests_thumbnail_variant(self):
        query = parse_qs(urlparse(self._photo().thumbnail_url).query)
        self.assertEqual(query["variant"], ["thumbnail"])

    def test_original_delivery_is_explicit(self):
        query = parse_qs(urlparse(self._photo().original_delivery_url).query)
        self.assertEqual(query["variant"], ["original"])

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            signed_media_url("galleries/photo.jpg", variant="giant")

    def test_variant_does_not_change_signed_origin_path(self):
        preview = urlparse(signed_media_url("galleries/photo.jpg", now=100, variant="preview"))
        original = urlparse(signed_media_url("galleries/photo.jpg", now=100, variant="original"))
        self.assertEqual(preview.path, original.path)
        self.assertEqual(parse_qs(preview.query)["signature"], parse_qs(original.query)["signature"])
