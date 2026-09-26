import logging
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.core.observability import SensitiveDataFilter, redact


class OperationsObservabilityTests(SimpleTestCase):
    databases = {"default"}

    def test_request_id_is_returned_and_client_value_is_preserved(self):
        response = self.client.get("/health/live/", HTTP_X_REQUEST_ID="deploy-check-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-ID"], "deploy-check-123")

    def test_sensitive_assignments_are_redacted(self):
        text = redact("password=hunter2 token=abc123 access_key=key-123 harmless=value")
        self.assertNotIn("hunter2", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("key-123", text)
        self.assertIn("harmless=value", text)

    def test_logging_filter_redacts_message_arguments(self):
        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "failure token=%s", ("secret-token",), None)
        SensitiveDataFilter().filter(record)
        rendered = record.getMessage()
        self.assertNotIn("secret-token", rendered)
        self.assertIn("[REDACTED]", rendered)
        self.assertTrue(record.request_id)

    @override_settings(
        GALLERY_STORAGE_BACKEND="b2",
        B2_BUCKET_NAME="private-bucket",
        B2_ACCESS_KEY_ID="id",
        B2_SECRET_ACCESS_KEY="secret",
        B2_REGION="us-west-004",
        B2_ENDPOINT_URL="https://example.invalid",
    )
    def test_readiness_checks_b2_without_leaking_provider_error(self):
        redis = MagicMock()
        storage = MagicMock()
        storage.bucket.meta.client.head_bucket.side_effect = RuntimeError("secret B2 endpoint credential")
        with patch("apps.core.health.Redis.from_url", return_value=redis), patch(
            "apps.core.health.gallery_photo_storage", return_value=storage
        ):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn(b"credential", response.content.lower())
        storage.bucket.meta.client.head_bucket.assert_called_once_with(Bucket="private-bucket")

    def test_broker_outage_makes_readiness_unavailable(self):
        with patch("apps.core.health.Redis.from_url", side_effect=RuntimeError("broker password=secret")):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn(b"secret", response.content.lower())
