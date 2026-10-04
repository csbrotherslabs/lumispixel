import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
REDIS_CA_PATH = "/etc/lumispixel/certs/redis_ca.pem"
REDIS_TLS_QUERY = (
    "ssl_cert_reqs=required"
    f"&ssl_ca_certs={quote(REDIS_CA_PATH, safe='')}"
)
REDIS_TLS_URL = f"rediss://redis.example.com/0?{REDIS_TLS_QUERY}"


class ProductionConfigurationContractTests(SimpleTestCase):
    def _check(self, overrides=None):
        env = os.environ.copy()
        env.update({
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": "x" * 50,
            "DJANGO_ALLOWED_HOSTS": "lumispixel.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://lumispixel.com",
            "DJANGO_PUBLIC_BASE_URL": "https://lumispixel.com",
            "DATABASE_URL": "postgresql://user:password@db.example.com/lumispixel",
            "DB_SSL_REQUIRE": "1",
            "GALLERY_STORAGE_BACKEND": "b2",
            "GALLERY_STORAGE_ENVIRONMENT": "prod",
            "B2_ACCESS_KEY_ID": "key-id",
            "B2_SECRET_ACCESS_KEY": "secret",
            "B2_BUCKET_NAME": "bucket",
            "B2_REGION": "us-east-005",
            "B2_ENDPOINT_URL": "https://s3.us-east-005.backblazeb2.com",
            "MEDIA_DELIVERY_BASE_URL": "https://media.lumispixel.com",
            "MEDIA_SIGNING_SECRET": "m" * 40,
            "DJANGO_EMAIL_HOST": "smtp.example.com",
            "DJANGO_EMAIL_HOST_USER": "smtp-user",
            "DJANGO_EMAIL_HOST_PASSWORD": "smtp-password",
            "DJANGO_EMAIL_USE_TLS": "1",
            "DJANGO_EMAIL_USE_SSL": "0",
            "CELERY_BROKER_URL": REDIS_TLS_URL,
            "CELERY_RESULT_BACKEND": REDIS_TLS_URL,
        })
        if overrides:
            env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=ROOT, env=env, text=True, capture_output=True,
        )

    def test_valid_production_contract_loads(self):
        result = self._check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_rejects_non_postgresql_database(self):
        result = self._check({"DATABASE_URL": "sqlite:///db.sqlite3"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must use PostgreSQL", result.stderr)

    def test_production_rejects_insecure_redis(self):
        result = self._check({"CELERY_BROKER_URL": "redis://redis.example.com/0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must use rediss://", result.stderr)

    def test_production_requires_email_credentials(self):
        result = self._check({"DJANGO_EMAIL_HOST_PASSWORD": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SMTP host and credentials are required", result.stderr)

    def test_production_rejects_insecure_b2_endpoint(self):
        result = self._check({"B2_ENDPOINT_URL": "http://b2.example.com"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("B2_ENDPOINT_URL must use HTTPS", result.stderr)

    def test_b2_user_uploads_require_complete_configuration(self):
        result = self._check({"USER_UPLOAD_STORAGE_BACKEND": "b2", "B2_SITE_BUCKET_NAME": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("user upload buckets", result.stderr)

    def test_b2_user_uploads_reject_dev_buckets_in_production(self):
        result = self._check({
            "USER_UPLOAD_STORAGE_BACKEND": "b2",
            "B2_SITE_BUCKET_NAME": "lumispixel-dev-site-media",
            "B2_PRIVATE_UPLOAD_BUCKET_NAME": "lumispixel-prod-private-media",
            "UPLOAD_B2_ACCESS_KEY_ID": "key", "UPLOAD_B2_SECRET_ACCESS_KEY": "secret",
            "SITE_MEDIA_DELIVERY_BASE_URL": "https://site-media.lumispixel.com",
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must match the dev/prod environment", result.stderr)

    def test_b2_user_uploads_valid_configuration_loads(self):
        result = self._check({
            "USER_UPLOAD_STORAGE_BACKEND": "b2",
            "B2_SITE_BUCKET_NAME": "lumispixel-prod-site-media",
            "B2_PRIVATE_UPLOAD_BUCKET_NAME": "lumispixel-prod-private-media",
            "UPLOAD_B2_ACCESS_KEY_ID": "key", "UPLOAD_B2_SECRET_ACCESS_KEY": "secret",
            "SITE_MEDIA_DELIVERY_BASE_URL": "https://site-media.lumispixel.com",
        })
        self.assertEqual(result.returncode, 0, result.stderr)
