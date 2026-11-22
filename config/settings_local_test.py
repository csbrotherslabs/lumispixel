"""Local SQLite test settings. Never connects to production PostgreSQL."""

from .settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
# Browser tests use StaticLiveServerTestCase, which serves source static assets
# directly. Do not emit manifest-hashed URLs that only collectstatic can serve.
DEBUG = True
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
