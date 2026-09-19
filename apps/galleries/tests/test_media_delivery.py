import base64
import hashlib
import hmac
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, override_settings

from apps.galleries.media_delivery import signed_media_url


@override_settings(
    GALLERY_STORAGE_ENVIRONMENT="dev",
    MEDIA_DELIVERY_BASE_URL="https://media-dev.lumispixel.com",
    MEDIA_SIGNING_SECRET="test-media-secret",
    MEDIA_SIGNED_URL_TTL=900,
)
class SignedMediaUrlTests(SimpleTestCase):
    def test_generates_worker_compatible_signature(self):
        url = signed_media_url(
            "galleries/2/3/originals/photo name.png",
            now=1_700_000_000,
        )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual(
            parsed.path,
            "/private/dev/galleries/2/3/originals/photo%20name.png",
        )
        self.assertEqual(query["expires"], ["1700000900"])

        payload = f"{parsed.path}\n1700000900".encode()
        digest = hmac.new(b"test-media-secret", payload, hashlib.sha256).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        self.assertEqual(query["signature"], [expected])

    def test_rejects_ttl_longer_than_worker_limit(self):
        with self.assertRaises(ValueError):
            signed_media_url("galleries/2/3/originals/photo.png", ttl=3601, now=1)
