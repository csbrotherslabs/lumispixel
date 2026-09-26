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

# Do not carry a persistent physical database connection across test/request
# boundaries. The production settings intentionally use CONN_MAX_AGE, but a
# long-running test process contains failure-injection tests and response
# lifecycle hooks that may close the underlying psycopg connection. Reusing
# that stale physical connection poisons every later TestCase with
# "psycopg.OperationalError: the connection is closed". Keeping persistent
# connections disabled in the test runner preserves PostgreSQL transaction,
# locking, constraint, and migration semantics while giving each test/request
# boundary a clean connection lifecycle.
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
GALLERY_STORAGE_BACKEND = "local"
GALLERY_STORAGE_ENVIRONMENT = "dev"
