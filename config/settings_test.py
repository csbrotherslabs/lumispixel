"""Settings used by the automated Django test suite."""

import os
from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403,F401

# Tests render templates directly and do not run collectstatic. Using the
# non-manifest backend keeps static() resolution deterministic while leaving
# production on WhiteNoise's CompressedManifestStaticFilesStorage.
STORAGES = {  # noqa: F405
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
GALLERY_STORAGE_BACKEND = "local"
GALLERY_STORAGE_ENVIRONMENT = "dev"

# Production uses a finite persistent-connection lifetime, but long-running
# TestCase transactions must not have their PostgreSQL connection retired by
# request/response cleanup partway through the suite. Let Django's test runner
# own the connection lifecycle instead. Keep health checks enabled so the test
# environment preserves the production database connection contract.
DATABASES["default"]["CONN_MAX_AGE"] = None  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# SQLite is opt-in for lightweight unit tests when managed PostgreSQL users
# cannot create a temporary test database. Existing PostgreSQL CI behavior
# remains unchanged unless this flag is explicitly set.
if env_bool("LUMISPIXEL_TEST_SQLITE", False):  # noqa: F405
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test_visual_search.sqlite3",  # noqa: F405
            "TEST": {"NAME": ":memory:"},
        }
    }

# Explicit local PostgreSQL configuration takes precedence over inherited URLs.
# CI may retain its existing loopback service URL; never use a remote database.
if not env_bool("LUMISPIXEL_TEST_SQLITE", False):
    if os.getenv("TEST_DB_NAME") or not env_bool("CI", False):
        host = os.getenv("TEST_DB_HOST", "127.0.0.1")
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ImproperlyConfigured("TEST_DB_HOST must be a loopback address.")
        name = os.getenv("TEST_DB_NAME", "lumispixel_local")
        user = os.getenv("TEST_DB_USER", "lumispixel_test")
        password = os.getenv("TEST_DB_PASSWORD", "")
        if not name or not user or not password:
            raise ImproperlyConfigured("Configure TEST_DB_NAME, TEST_DB_USER and TEST_DB_PASSWORD for local PostgreSQL tests.")
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": host,
                "PORT": os.getenv("TEST_DB_PORT", "5432"),
                "NAME": name,
                "USER": user,
                "PASSWORD": password,
                "CONN_MAX_AGE": None,
                "CONN_HEALTH_CHECKS": True,
                "TEST": {"NAME": "test_" + name},
            }
        }
    else:
        db = DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.postgresql" or db.get("HOST") not in ("127.0.0.1", "localhost", "::1"):
            raise ImproperlyConfigured("CI PostgreSQL tests require a loopback database.")

# Prevent inherited API credentials from sending real transactional emails.
TRANSACTIONAL_EMAIL_TRANSPORT = "smtp"
BREVO_API_KEY = ""

# Ephemeral test-only encryption key; never depend on deployed secrets.
from cryptography.fernet import Fernet
EMAIL_PAYLOAD_KEYS = Fernet.generate_key().decode("ascii")

# Recovery links require a trusted absolute origin, even when DEBUG is false.
PUBLIC_BASE_URL = "https://lumispixel.example"

# Ordinary tests must not inherit external infrastructure.
USER_UPLOAD_STORAGE_BACKEND = "local"
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
VISUAL_SEARCH_DATABASE_URL = ""

# Never allow inherited remote storage credentials in ordinary tests.
B2_ACCESS_KEY_ID = B2_SECRET_ACCESS_KEY = B2_BUCKET_NAME = ""
B2_SITE_ACCESS_KEY_ID = B2_SITE_SECRET_ACCESS_KEY = B2_SITE_BUCKET_NAME = ""
B2_PRIVATE_UPLOAD_ACCESS_KEY_ID = B2_PRIVATE_UPLOAD_SECRET_ACCESS_KEY = B2_PRIVATE_UPLOAD_BUCKET_NAME = ""
B2_ENDPOINT_URL = B2_REGION = ""
MEDIA_SIGNING_SECRET = "test-only-gallery-signing-secret-not-for-deployment"
