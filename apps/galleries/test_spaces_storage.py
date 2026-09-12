from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Gallery, GalleryPhoto
from apps.galleries.storage import PrivateGallerySpacesStorage, gallery_photo_storage


SPACES_SETTINGS = {
    "USE_SPACES": True,
    "SPACES_ACCESS_KEY": "test-access-key",
    "SPACES_SECRET_KEY": "test-secret-key",
    "SPACES_BUCKET_NAME": "lumispixel-test",
    "SPACES_REGION": "nyc3",
    "SPACES_ENDPOINT_URL": "https://nyc3.digitaloceanspaces.com",
    "SPACES_SIGNED_URL_TTL": 321,
    "SPACES_ENVIRONMENT": "dev",
}


class GallerySpacesStorageConfigurationTests(SimpleTestCase):
    @override_settings(**SPACES_SETTINGS)
    def test_spaces_enabled_never_falls_back_to_local_storage(self):
        with patch("apps.galleries.storage.FileSystemStorage") as local_storage:
            storage = gallery_photo_storage()

        local_storage.assert_not_called()
        self.assertIsInstance(storage, PrivateGallerySpacesStorage)
        self.assertEqual(storage.bucket_name, "lumispixel-test")
        self.assertEqual(storage.endpoint_url, "https://nyc3.digitaloceanspaces.com")
        self.assertEqual(storage.location, "private/dev")
        self.assertEqual(storage.default_acl, "private")
        self.assertTrue(storage.querystring_auth)
        self.assertEqual(storage.querystring_expire, 321)
        self.assertFalse(storage.file_overwrite)

    @override_settings(**{**SPACES_SETTINGS, "SPACES_ENVIRONMENT": "prod"})
    def test_prod_uses_separate_spaces_prefix(self):
        storage = gallery_photo_storage()
        self.assertEqual(storage.location, "private/prod")

    @override_settings(**SPACES_SETTINGS)
    def test_spaces_filename_adds_originals_namespace(self):
        storage = gallery_photo_storage()
        generated = storage.generate_filename("galleries/12/87/photo.jpg")
        self.assertEqual(generated, "galleries/12/87/originals/photo.jpg")

    @override_settings(
        USE_SPACES=True,
        SPACES_ACCESS_KEY="",
        SPACES_SECRET_KEY="",
        SPACES_BUCKET_NAME="",
        SPACES_ENVIRONMENT="dev",
    )
    def test_spaces_enabled_fails_closed_when_credentials_are_missing(self):
        with patch("apps.galleries.storage.FileSystemStorage") as local_storage:
            with self.assertRaises(ImproperlyConfigured):
                gallery_photo_storage()

        local_storage.assert_not_called()

    @override_settings(**{**SPACES_SETTINGS, "SPACES_ENVIRONMENT": "staging"})
    def test_unknown_environment_fails_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            gallery_photo_storage()

    def test_gallery_photo_field_is_wired_to_storage_resolver(self):
        field = GalleryPhoto._meta.get_field("file")
        self.assertIs(field._storage_callable, gallery_photo_storage)


@override_settings(**SPACES_SETTINGS)
class GallerySpacesUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="spaces-photographer@example.com",
            password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            slug="spaces-photographer",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.photographer,
            name="Spaces proof gallery",
            slug="spaces-proof-gallery",
            status=Gallery.Status.DRAFT,
        )
        self.client.force_login(self.user)

    @staticmethod
    def jpeg_upload():
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "white").save(buffer, format="JPEG")
        return SimpleUploadedFile(
            "spaces-proof.jpg",
            buffer.getvalue(),
            content_type="image/jpeg",
        )

    def test_upload_queue_writes_gallery_photo_through_spaces_storage(self):
        spaces_storage = gallery_photo_storage()
        field = GalleryPhoto._meta.get_field("file")

        with (
            patch.object(field, "storage", spaces_storage),
            patch.object(spaces_storage, "exists", return_value=False),
            patch.object(spaces_storage, "_save", side_effect=lambda name, content: name) as spaces_save,
            patch("apps.galleries.storage.FileSystemStorage") as local_storage,
        ):
            response = self.client.post(
                reverse("photographer_workspace:gallery_upload_queue"),
                {"gallery": str(self.gallery.pk), "files": [self.jpeg_upload()]},
            )

        self.assertEqual(response.status_code, 201)
        local_storage.assert_not_called()
        spaces_save.assert_called_once()
        saved_name = spaces_save.call_args.args[0]
        self.assertEqual(
            saved_name,
            f"galleries/{self.photographer.pk}/{self.gallery.pk}/originals/spaces-proof.jpg",
        )
        self.assertEqual(
            f"{spaces_storage.location}/{saved_name}",
            f"private/dev/galleries/{self.photographer.pk}/{self.gallery.pk}/originals/spaces-proof.jpg",
        )

        photo = GalleryPhoto.objects.get(gallery=self.gallery)
        self.assertEqual(photo.file.name, saved_name)
        self.assertEqual(photo.status, GalleryPhoto.Status.COMPLETED)
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.image_count, 1)
        self.assertEqual(self.gallery.storage_used, photo.file_size)
