import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.galleries.media_delivery import signed_media_url


class MediaDeliveryContractTests(SimpleTestCase):
    @override_settings(
        GALLERY_STORAGE_ENVIRONMENT="prod",
        MEDIA_DELIVERY_BASE_URL="https://media.lumispixel.com",
        MEDIA_SIGNING_SECRET="x" * 32,
        MEDIA_SIGNED_URL_TTL=900,
    )
    def test_signed_url_uses_private_prod_path_and_stable_contract(self):
        url = signed_media_url(
            "galleries/7/11/originals/photo name.jpg",
            now=1_700_000_000,
        )
        self.assertTrue(url.startswith(
            "https://media.lumispixel.com/private/prod/galleries/7/11/originals/photo%20name.jpg?"
        ))
        self.assertIn("expires=1700000900", url)
        self.assertIn("signature=", url)
        self.assertNotIn(" ", url)

    @override_settings(
        GALLERY_STORAGE_ENVIRONMENT="prod",
        MEDIA_DELIVERY_BASE_URL="https://media.lumispixel.com",
        MEDIA_SIGNING_SECRET="x" * 32,
    )
    def test_signed_url_never_exposes_b2_credentials_or_endpoint(self):
        url = signed_media_url("galleries/1/2/originals/photo.jpg", now=1_700_000_000)
        self.assertNotIn("backblazeb2", url)
        self.assertNotIn("X-Amz-Credential", url)
