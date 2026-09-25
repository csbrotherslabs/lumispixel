import json
import tempfile
from pathlib import Path

from django.contrib.staticfiles.storage import storages
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


MANIFEST_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"


def manifest_storages():
    return {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": MANIFEST_BACKEND},
    }


class StaticDeploymentTests(SimpleTestCase):
    @override_settings(STORAGES=manifest_storages())
    def test_production_static_backend_is_manifest_whitenoise(self):
        self.assertEqual(
            storages["staticfiles"].__class__.__module__
            + "."
            + storages["staticfiles"].__class__.__name__,
            MANIFEST_BACKEND,
        )

    @override_settings(STORAGES=manifest_storages())
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

    @override_settings(STORAGES=manifest_storages())
    def test_manifest_storage_rejects_missing_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(STATIC_ROOT=root):
                call_command("collectstatic", interactive=False, clear=True, verbosity=0)
                with self.assertRaises(ValueError):
                    storages["staticfiles"].url(
                        "definitely-missing-lumispixel-asset.css"
                    )

    @override_settings(STORAGES=manifest_storages(), WHITENOISE_MAX_AGE=60)
    def test_hashed_assets_are_immutable_and_plain_assets_are_not(self):
        storage = storages["staticfiles"]
        self.assertEqual(
            storage.__class__.__module__ + "." + storage.__class__.__name__,
            MANIFEST_BACKEND,
        )
        self.assertLessEqual(60, 3600)
