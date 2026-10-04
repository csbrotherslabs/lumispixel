import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import InMemoryStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.models import ClientProfile, User
from apps.core.upload_storage import UploadB2Storage, UserUploadStorage

B2_CONFIG = dict(
    B2_SITE_ACCESS_KEY_ID="site-key", B2_SITE_SECRET_ACCESS_KEY="site-secret",
    B2_PRIVATE_UPLOAD_ACCESS_KEY_ID="private-key", B2_PRIVATE_UPLOAD_SECRET_ACCESS_KEY="private-secret",
    B2_SITE_BUCKET_NAME="lumispixel-dev-site-media",
    B2_PRIVATE_UPLOAD_BUCKET_NAME="lumispixel-dev-private-media",
    B2_REGION="us-east-005", B2_ENDPOINT_URL="https://s3.us-east-005.backblazeb2.com",
    GALLERY_STORAGE_ENVIRONMENT="dev",
    SITE_MEDIA_DELIVERY_BASE_URL="https://site-media-dev.lumispixel.com",
    MEDIA_SIGNED_URL_TTL=900,
)


@override_settings(**B2_CONFIG)
class UserUploadStorageTests(SimpleTestCase):
    def test_site_image_urls_are_stable_and_environment_partitioned(self):
        storage = UserUploadStorage()
        name = "client-profiles/avatar.png"
        self.assertEqual(storage.url(name), "https://site-media-dev.lumispixel.com/site/dev/client-profiles/avatar.png")
        self.assertEqual(storage.site.bucket_name, "lumispixel-dev-site-media")
        self.assertIsNone(storage.site.default_acl)
        self.assertEqual(storage.site.access_key, "site-key")
        self.assertEqual(storage.site.secret_key, "site-secret")
        self.assertEqual(storage.private.access_key, "private-key")
        self.assertEqual(storage.private.secret_key, "private-secret")

    def test_unknown_paths_and_gallery_covers_remain_restricted(self):
        storage = UserUploadStorage()
        for name in ("support/report.png", "contracts/1/signed.pdf", "galleries/covers/a.jpg", "client-profiles/report.html", "clients/profile_photos/2026/avatar.png"):
            with self.subTest(name=name):
                backend = storage.backend_for(name)
                self.assertFalse(backend.site)
                url = urlparse(backend.url(name))
                self.assertIn("X-Amz-Signature", parse_qs(url.query))
                self.assertIn("/uploads/dev/", url.path)
                self.assertEqual(backend.bucket_name, "lumispixel-dev-private-media")

    def test_public_backend_rejects_restricted_paths_and_traversal(self):
        storage = UploadB2Storage(site=True)
        for name in ("contracts/1/signed.pdf", "../client-profiles/avatar.png", "/client-profiles/avatar.png"):
            with self.assertRaises(SuspiciousFileOperation):
                storage.url(name)

    def test_new_keys_are_unique_without_overwriting_original(self):
        storage = UserUploadStorage()
        first = storage.get_available_name("photographer_websites/2/hero/photo.JPG", 100)
        second = storage.get_available_name("photographer_websites/2/hero/photo.JPG", 100)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("photographer_websites/2/hero/"))
        self.assertTrue(first.endswith(".jpg"))


class UploadMigrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="upload@example.com", password="testing-password")
        self.profile = ClientProfile.objects.create(user=self.user, profile_photo="client-profiles/avatar.png")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / self.profile.profile_photo.name
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"existing-image")

    @override_settings(USER_UPLOAD_STORAGE_BACKEND="b2")
    def test_migration_is_verified_repeatable_and_preserves_source_and_reference(self):
        remote = InMemoryStorage()
        with patch("apps.core.management.commands.migrate_user_uploads_to_b2.UserUploadStorage") as factory:
            factory.return_value.backend_for.return_value = remote
            for _ in range(2):
                call_command("migrate_user_uploads_to_b2", apply=True, source_root=str(self.root))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.profile_photo.name, "client-profiles/avatar.png")
        self.assertEqual(remote.open(self.profile.profile_photo.name).read(), b"existing-image")
        self.assertTrue(self.source.exists())

    def test_missing_file_blocks_cutover(self):
        self.source.unlink()
        with self.assertRaises(CommandError):
            call_command("migrate_user_uploads_to_b2", source_root=str(self.root))

    @override_settings(USER_UPLOAD_STORAGE_BACKEND="b2")
    def test_existing_destination_mismatch_is_not_overwritten(self):
        from django.core.files.base import ContentFile
        remote = InMemoryStorage()
        remote.save(self.profile.profile_photo.name, ContentFile(b"different-image"))
        with patch("apps.core.management.commands.migrate_user_uploads_to_b2.UserUploadStorage") as factory:
            factory.return_value.backend_for.return_value = remote
            with self.assertRaises(CommandError):
                call_command("migrate_user_uploads_to_b2", apply=True, source_root=str(self.root))
        self.assertEqual(remote.open(self.profile.profile_photo.name).read(), b"different-image")


@override_settings(**B2_CONFIG)
class RemoteProfileSessionTests(TestCase):
    @override_settings(STORAGES={
        "default": {"BACKEND": "apps.core.upload_storage.UserUploadStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_uploaded_photo_persists_after_logout_and_login_without_local_media(self):
        from django.core.files.base import ContentFile
        from django.urls import reverse
        from apps.accounts.models import PhotographerProfile

        class RemoteMemoryStorage(InMemoryStorage):
            def url(self, name):
                return "https://site-media-dev.lumispixel.com/site/dev/" + name

        remote = RemoteMemoryStorage()
        with patch("apps.core.upload_storage.UploadB2Storage", return_value=remote):
            user = User.objects.create_user(
                email="remote-avatar@example.com", password="TestPass123!",
                account_status=User.AccountStatus.ACTIVE, email_verified=True,
                primary_role=User.PrimaryRole.PHOTOGRAPHER,
                last_active_workspace=User.Workspace.PHOTOGRAPHER,
            )
            PhotographerProfile.objects.create(user=user, onboarding_completed=True)
            profile = ClientProfile.objects.create(user=user)
            profile.profile_photo.save("avatar.png", ContentFile(b"remote-image"))
            expected = profile.profile_photo.url
            self.assertTrue(remote.exists(profile.profile_photo.name))
            self.client.force_login(user)
            self.assertContains(self.client.get(reverse("photographer_workspace:dashboard")), expected)
            self.client.logout()
            self.assertTrue(self.client.login(email=user.email, password="TestPass123!"))
            for page in ("dashboard", "profile"):
                self.assertContains(self.client.get(reverse(f"photographer_workspace:{page}")), expected)
