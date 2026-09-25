"""Production configuration and accidental-secret regression tests."""
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class RepositorySecretHygieneTests(SimpleTestCase):
    def test_environment_files_are_ignored_except_example(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env\n", gitignore)
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_example_environment_contains_no_secret_values(self):
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        sensitive = (
            "B2_SECRET_ACCESS_KEY", "DJANGO_EMAIL_HOST_PASSWORD",
            "MEDIA_SIGNING_SECRET", "DATABASE_URL",
        )
        values = {}
        for line in example.splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        for key in sensitive:
            if key in values:
                self.assertIn(values[key], {"", "change-me"}, f"{key} must not contain a credential")

    def test_no_tracked_dotenv_secret_files(self):
        result = subprocess.run(
            ["git", "ls-files", ".env", ".env.*"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        self.assertEqual(tracked, {".env.example", ".env.production.example"})


class ProductionConfigurationTests(SimpleTestCase):
    def run_settings(self, **overrides):
        env = os.environ.copy()
        env.update({
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": "production-test-secret-key-not-real-123456789",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/lumispixel",
            "GALLERY_STORAGE_BACKEND": "b2",
            "GALLERY_STORAGE_ENVIRONMENT": "prod",
            "B2_ACCESS_KEY_ID": "test-key-id",
            "B2_SECRET_ACCESS_KEY": "test-secret",
            "B2_BUCKET_NAME": "test-private-bucket",
            "B2_REGION": "us-west-004",
            "B2_ENDPOINT_URL": "https://s3.us-west-004.backblazeb2.com",
            "MEDIA_DELIVERY_BASE_URL": "https://media.example.test",
            "MEDIA_SIGNING_SECRET": "media-signing-test-secret-at-least-32-chars",
            "DJANGO_EMAIL_HOST": "smtp.example.test",
            "DJANGO_EMAIL_HOST_USER": "smtp-user",
            "DJANGO_EMAIL_HOST_PASSWORD": "smtp-password",
            "DJANGO_EMAIL_USE_TLS": "1",
            "DJANGO_EMAIL_USE_SSL": "0",
            "CELERY_BROKER_URL": "rediss://redis.example.test/0",
            "CELERY_RESULT_BACKEND": "rediss://redis.example.test/0",
        })
        env.update(overrides)
        code = (
            "import config.settings as s;"
            "print(s.DEBUG, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE,"
            "s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS,"
            "s.SECURE_HSTS_INCLUDE_SUBDOMAINS, s.SECURE_CONTENT_TYPE_NOSNIFF,"
            "s.X_FRAME_OPTIONS)"
        )
        return subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env,
            capture_output=True, text=True,
        )

    def test_production_security_headers_and_cookie_contract(self):
        result = self.run_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().split()
        self.assertEqual(values[0:4], ["False", "True", "True", "True"])
        self.assertGreater(int(values[4]), 0)
        self.assertEqual(values[5:], ["True", "True", "DENY"])

    def test_production_rejects_development_secret_key(self):
        result = self.run_settings(DJANGO_SECRET_KEY="django-insecure-development-only-change-me")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY must be set in production", result.stderr)

    def test_production_rejects_local_gallery_storage(self):
        result = self.run_settings(GALLERY_STORAGE_BACKEND="local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production requires GALLERY_STORAGE_BACKEND=b2", result.stderr)

    def test_production_rejects_dev_storage_namespace(self):
        result = self.run_settings(GALLERY_STORAGE_ENVIRONMENT="dev")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production requires GALLERY_STORAGE_ENVIRONMENT=prod", result.stderr)

    def test_production_rejects_missing_media_signing_secret(self):
        result = self.run_settings(MEDIA_SIGNING_SECRET="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MEDIA_SIGNING_SECRET is required", result.stderr)

    def test_production_rejects_short_media_signing_secret(self):
        result = self.run_settings(MEDIA_SIGNING_SECRET="short")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 32 characters", result.stderr)

    def test_production_rejects_http_media_delivery(self):
        result = self.run_settings(MEDIA_DELIVERY_BASE_URL="http://media.example.test")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must use HTTPS", result.stderr)

    def test_b2_backend_rejects_missing_credentials(self):
        result = self.run_settings(B2_SECRET_ACCESS_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("B2_ACCESS_KEY_ID", result.stderr)

    def test_production_rejects_missing_database(self):
        result = self.run_settings(DATABASE_URL="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL must be set in production", result.stderr)
