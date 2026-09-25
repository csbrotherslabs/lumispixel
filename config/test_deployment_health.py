from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


class DeploymentHealthTests(SimpleTestCase):
    databases = {"default"}

    def test_liveness_does_not_require_dependencies(self):
        response = self.client.get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_readiness_is_generic_and_healthy_when_dependencies_respond(self):
        redis = MagicMock()
        redis.ping.return_value = True
        with patch("apps.core.health.Redis.from_url", return_value=redis):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        redis.ping.assert_called_once()

    def test_readiness_returns_503_without_leaking_dependency_details(self):
        with patch("apps.core.health.Redis.from_url", side_effect=RuntimeError("redis secret host")):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn(b"redis", response.content.lower())
        self.assertNotIn(b"postgres", response.content.lower())

    @override_settings(CELERY_BROKER_URL="redis://example.invalid/0")
    def test_readiness_uses_short_redis_timeouts(self):
        redis = MagicMock()
        with patch("apps.core.health.Redis.from_url", return_value=redis) as factory:
            self.client.get("/health/ready/")
        factory.assert_called_once_with(
            "redis://example.invalid/0",
            socket_connect_timeout=2,
            socket_timeout=2,
        )
