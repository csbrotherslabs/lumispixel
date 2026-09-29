from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase


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

    def test_production_contract_does_not_point_at_local_redis(self):
        env = self._production_env()
        for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
            with self.subTest(key=key):
                hostname = urlparse(env[key]).hostname
                self.assertNotIn(hostname, {"127.0.0.1", "localhost"})
