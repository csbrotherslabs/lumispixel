from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from config.celery import validate_production_redis_tls


class ProductionRedisTLSContractTests(SimpleTestCase):
    def _production_env(self):
        env_path = Path(__file__).resolve().parents[2] / ".env.production.example"
        values = {}
        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
        return values

    def test_celery_redis_urls_require_tls_and_ca_verification(self):
        env = self._production_env()

        for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
            with self.subTest(key=key):
                parsed = urlparse(env[key])
                query = parse_qs(parsed.query)

                self.assertEqual(parsed.scheme, "rediss")
                self.assertEqual(query.get("ssl_cert_reqs"), ["required"])
                self.assertEqual(
                    query.get("ssl_ca_certs"),
                    ["/etc/lumispixel/certs/redis_ca.pem"],
                )
                validate_production_redis_tls(env[key], key)

    def test_production_contract_does_not_point_at_local_redis(self):
        env = self._production_env()
        for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
            with self.subTest(key=key):
                hostname = urlparse(env[key]).hostname
                self.assertNotIn(hostname, {"127.0.0.1", "localhost"})

    def test_validation_rejects_unencrypted_redis(self):
        with self.assertRaisesRegex(RuntimeError, "rediss"):
            validate_production_redis_tls(
                "redis://localhost:6379/0",
                "CELERY_BROKER_URL",
            )

    def test_validation_rejects_disabled_certificate_verification(self):
        with self.assertRaisesRegex(RuntimeError, "ssl_cert_reqs=required"):
            validate_production_redis_tls(
                "rediss://default:secret@example.invalid:6380/0?ssl_cert_reqs=none&ssl_ca_certs=%2Ftmp%2Fca.pem",
                "CELERY_BROKER_URL",
            )

    def test_validation_requires_ca_certificate(self):
        with self.assertRaisesRegex(RuntimeError, "ssl_ca_certs"):
            validate_production_redis_tls(
                "rediss://default:secret@example.invalid:6380/0?ssl_cert_reqs=required",
                "CELERY_RESULT_BACKEND",
            )
