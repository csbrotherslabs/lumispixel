import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class StaticDeploymentTests(SimpleTestCase):
    def test_production_static_backend_is_manifest_whitenoise(self):
        self.assertEqual(
            settings.STATICFILES_STORAGE_BACKEND,
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_collectstatic_builds_manifest_with_hashed_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(STATIC_ROOT=root):
                call_command("collectstatic", interactive=False, clear=True, verbosity=0)
                manifest_path = root / "staticfiles.json"
                self.assertTrue(manifest_path.exists())
                manifest = json.loads(manifest_path.read_text())
                self.assertTrue(manifest["paths"])
                source, hashed = next(
                    (source, hashed)
                    for source, hashed in manifest["paths"].items()
                    if source != hashed
                )
                self.assertNotEqual(source, hashed)
                self.assertTrue((root / hashed).exists())

    def test_manifest_storage_rejects_missing_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(STATIC_ROOT=root):
                call_command("collectstatic", interactive=False, clear=True, verbosity=0)
                with self.assertRaises(ValueError):
                    staticfiles_storage.url("definitely-missing-lumispixel-asset.css")

    def test_hashed_assets_are_immutable_and_plain_assets_are_not(self):
        immutable = settings.STATICFILES_STORAGE_BACKEND.endswith(
            "CompressedManifestStaticFilesStorage"
        )
        self.assertTrue(immutable)
        self.assertLessEqual(settings.WHITENOISE_MAX_AGE, 3600)
