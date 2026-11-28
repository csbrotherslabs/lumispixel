"""Opt-in local infrastructure integration settings; never use in production."""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from .settings_test import *  # noqa: F403,F401

if not DEBUG or os.getenv("LUMISPIXEL_INTEGRATION_ENABLED") != "1":
    raise ImproperlyConfigured("Explicit local integration opt-in required.")
db = DATABASES["default"]
if (db.get("ENGINE") != "django.db.backends.postgresql"
        or db.get("HOST") not in ("localhost", "127.0.0.1", "::1")
        or db.get("NAME") != "lumispixel_integration"):
    raise ImproperlyConfigured("Use the dedicated local lumispixel_integration database.")

# Separate Redis instance, not merely separate logical databases.
CELERY_BROKER_URL = "redis://127.0.0.1:6380/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6380/1"
CELERY_TASK_DEFAULT_QUEUE = "celery"
EMAIL_PAYLOAD_KEYS = os.getenv("LUMISPIXEL_INTEGRATION_EMAIL_KEY", "")
try:
    Fernet(EMAIL_PAYLOAD_KEYS.encode("ascii"))
except (ValueError, TypeError, UnicodeError) as exc:
    raise ImproperlyConfigured("A shared test-only Fernet key is required.") from exc

# Keep cloud storage and vector access disabled for worker smoke tests.
# Real-photo tests explicitly override the vector URL inside their test case.
# Use a file sink to inspect synthetic messages across processes.
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
INTEGRATION_DATA_ROOT = Path.home() / "LumisPixelTestData" / "integration"
MEDIA_ROOT = INTEGRATION_DATA_ROOT / "media"
EMAIL_FILE_PATH = INTEGRATION_DATA_ROOT / "email"
