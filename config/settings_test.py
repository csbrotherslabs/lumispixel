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
