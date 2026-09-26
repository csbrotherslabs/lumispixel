"""Settings used by the automated Django test suite."""

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

# Keep the PostgreSQL connection alive across test-client request boundaries.
# Django TestCase wraps each test in an outer transaction. request_finished
# runs database connection cleanup after every self.client request; with
# CONN_MAX_AGE=0 that cleanup closes the psycopg connection while the TestCase
# transaction is still active, so the next ORM query fails with
# "psycopg.OperationalError: the connection is closed". The normal application
# configuration already uses persistent, health-checked connections, so retain
# those semantics in tests instead of forcing a zero connection lifetime.
DATABASES["default"]["CONN_MAX_AGE"] = None  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
GALLERY_STORAGE_BACKEND = "local"
GALLERY_STORAGE_ENVIRONMENT = "dev"
