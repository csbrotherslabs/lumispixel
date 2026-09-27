from django.test import SimpleTestCase, override_settings

from apps.galleries.models import gallery_photo_path
from apps.galleries.multipart_uploads import multipart_object_key


class ImmutableGalleryObjectKeyTests(SimpleTestCase):
    def test_django_upload_path_uses_uuid_not_original_filename(self):
        class Photo:
            photographer_id = 7
            gallery_id = 11

        first = gallery_photo_path(Photo(), "client-final.jpg")
        second = gallery_photo_path(Photo(), "client-final.jpg")
        self.assertRegex(first, r"^galleries/7/11/[0-9a-f]{32}\.jpg$")
        self.assertNotEqual(first, second)
        self.assertNotIn("client-final", first)

    @override_settings(GALLERY_STORAGE_ENVIRONMENT="dev")
    def test_multipart_key_uses_uuid_and_canonical_mime_extension(self):
        key = multipart_object_key(
            photographer_id=7,
            gallery_id=11,
            original_name="misleading.png",
            content_type="image/jpeg",
        )
        self.assertRegex(
            key,
            r"^private/dev/galleries/7/11/originals/[0-9a-f]{32}\.jpg$",
        )
        self.assertNotIn("misleading", key)
