from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from apps.galleries import multipart_uploads


class ExternalRetryContractTests(SimpleTestCase):
    def test_b2_retry_budget_is_bounded(self):
        self.assertGreaterEqual(settings.B2_MAX_ATTEMPTS, 1)
        self.assertLessEqual(settings.B2_MAX_ATTEMPTS, 10)
        self.assertGreater(settings.B2_CONNECT_TIMEOUT_SECONDS, 0)
        self.assertGreater(settings.B2_READ_TIMEOUT_SECONDS, 0)

    def test_celery_broker_retry_budget_is_bounded(self):
        self.assertIsInstance(settings.CELERY_BROKER_CONNECTION_MAX_RETRIES, int)
        self.assertGreaterEqual(settings.CELERY_BROKER_CONNECTION_MAX_RETRIES, 0)

    @patch("apps.galleries.multipart_uploads.boto3.client")
    def test_multipart_client_uses_standard_bounded_retries(self, client):
        with patch.object(settings, "GALLERY_STORAGE_BACKEND", "b2"):
            multipart_uploads._client()
        config = client.call_args.kwargs["config"]
        self.assertEqual(config.retries["mode"], "standard")
        self.assertEqual(config.retries["max_attempts"], settings.B2_MAX_ATTEMPTS)
        self.assertEqual(config.connect_timeout, settings.B2_CONNECT_TIMEOUT_SECONDS)
        self.assertEqual(config.read_timeout, settings.B2_READ_TIMEOUT_SECONDS)
