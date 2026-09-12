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
USE_SPACES = False
