from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from django.test import SimpleTestCase, override_settings
from . import brevo_transport as adapter

@override_settings(BREVO_API_KEY="test-only", DEFAULT_FROM_EMAIL="LumisPixel <sender@example.com>")
class BrevoTransportTests(SimpleTestCase):
    def send(self):
        return adapter.submit(subject="Test", plain_body="Body", html_body="", recipients=["client@example.com"], correlation="lp:test:1")

    @patch.object(adapter, "build_opener")
    def test_acceptance(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.status = 201
        response.read.return_value = b'{"messageId":"<test@example.com>"}'
        self.assertEqual(self.send(), "<test@example.com>")
        self.assertEqual(opener.return_value.open.call_count, 1)

    @patch.object(adapter, "build_opener")
    def test_throttle(self, opener):
        opener.return_value.open.side_effect = HTTPError("https://api.brevo.com", 429, "", {"Retry-After": "120"}, None)
        with self.assertRaises(adapter.ProviderThrottled) as error:
            self.send()
        self.assertEqual(error.exception.seconds, 120)

    @patch.object(adapter, "build_opener")
    def test_timeout_uncertain(self, opener):
        opener.return_value.open.side_effect = TimeoutError()
        with self.assertRaises(adapter.ProviderUncertain):
            self.send()
        self.assertEqual(opener.return_value.open.call_count, 1)

    @patch.object(adapter, "build_opener")
    def test_server_error_uncertain(self, opener):
        opener.return_value.open.side_effect = HTTPError("https://api.brevo.com", 503, "", {}, None)
        with self.assertRaises(adapter.ProviderUncertain):
            self.send()
