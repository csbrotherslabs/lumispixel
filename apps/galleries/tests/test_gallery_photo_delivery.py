from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.galleries.models import GalleryPhoto


@override_settings(
    GALLERY_STORAGE_ENVIRONMENT="dev",
    MEDIA_DELIVERY_BASE_URL="https://media-dev.lumispixel.com",
    MEDIA_SIGNING_SECRET="test-media-secret",
    MEDIA_SIGNED_URL_TTL=900,
)
class GalleryPhotoDeliveryUrlTests(SimpleTestCase):
    def test_delivery_url_uses_private_cloudflare_media_path(self):
        photo = GalleryPhoto()
        photo.file = "galleries/2/3/originals/example photo.png"

        with patch("apps.galleries.media_delivery.time.time", return_value=1_700_000_000):
            url = photo.delivery_url

        self.assertTrue(url.startswith(
            "https://media-dev.lumispixel.com/private/dev/galleries/2/3/originals/example%20photo.png?"
        ))
        self.assertIn("expires=1700000900", url)
        self.assertIn("&signature=", url)

    def test_delivery_url_is_empty_without_file(self):
        photo = GalleryPhoto()
        self.assertEqual(photo.delivery_url, "")
