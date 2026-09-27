import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


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
            "CELERY_BROKER_URL": "rediss://redis.example.com/0",
            "CELERY_RESULT_BACKEND": "rediss://redis.example.com/0",
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
