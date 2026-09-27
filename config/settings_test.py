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

# The production database configuration uses a finite persistent-connection
# lifetime. A long-running test process can outlive that lifetime while a
# TestCase transaction is still active. If a response is explicitly closed
# after the connection has aged out, Django's request_finished cleanup can
# close the transaction's underlying psycopg connection and poison the
# remaining tests with "the connection is closed". Test database lifecycle is
# already owned by Django's test runner, so do not age out the connection in
# the middle of the suite.
DATABASES["default"]["CONN_MAX_AGE"] = None  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = False  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
GALLERY_STORAGE_BACKEND = "local"
GALLERY_STORAGE_ENVIRONMENT = "dev"
