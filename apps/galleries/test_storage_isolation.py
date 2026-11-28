from unittest.mock import patch

from django.core.exceptions import SuspiciousFileOperation
from django.test import SimpleTestCase, override_settings

from . import multipart_uploads as multipart
from .media_delivery import signed_media_url
from .object_keys import validate_gallery_object_key


@override_settings(GALLERY_STORAGE_ENVIRONMENT="dev", GALLERY_STORAGE_BACKEND="b2",
                   MEDIA_SIGNING_SECRET="synthetic-test-secret",
                   MEDIA_DELIVERY_BASE_URL="https://media.example")
class GalleryStorageIsolationTests(SimpleTestCase):
    def test_valid_keys(self):
        for suffix in ("originals/photo.jpg", "variants/preview/photo.webp",
                       "variants/thumbnail/photo.webp"):
            key = "private/dev/galleries/1/2/" + suffix
            self.assertEqual(validate_gallery_object_key(key), key)

    def test_all_remote_operations_reject_invalid_keys_before_client(self):
        operations = (
            (multipart.initiate, {"content_type": "image/jpeg"}),
            (multipart.sign_part, {"upload_id": "test", "part_number": 1}),
            (multipart.list_parts, {"upload_id": "test"}),
            (multipart.get_object_stream, {}),
            (multipart.delete_object, {}),
            (multipart.complete, {"upload_id": "test", "parts": []}),
            (multipart.abort, {"upload_id": "test"}),
        )
        keys = (
            "private/prod/galleries/1/2/originals/photo.jpg",
            "private/development/galleries/1/2/originals/photo.jpg",
            "private/dev/../prod/photo.jpg",
            "private/dev/galleries/1/2/originals/%2e%2e",
            "private/dev/galleries/1/2/originals/../photo.jpg",
            "private/dev/galleries/1/2/originals//photo.jpg",
            "unknown/photo.jpg",
        )
        with patch.object(multipart, "_client") as client:
            for operation, kwargs in operations:
                for key in keys:
                    with self.subTest(operation=operation.__name__, key=key):
                        with self.assertRaises(SuspiciousFileOperation):
                            operation(key=key, **kwargs)
            client.assert_not_called()

    def test_production_rejects_development(self):
        with override_settings(GALLERY_STORAGE_ENVIRONMENT="prod"):
            with self.assertRaises(SuspiciousFileOperation):
                validate_gallery_object_key("private/dev/galleries/1/2/originals/photo.jpg")
            key = "private/prod/galleries/1/2/originals/photo.jpg"
            self.assertEqual(validate_gallery_object_key(key), key)

    def test_signed_media_rejects_malformed_paths(self):
        for name in ("../prod/photo.jpg", "/galleries/1/2/originals/photo.jpg",
                     "galleries/1/2/originals/%2e%2e", "private/prod/photo.jpg"):
            with self.subTest(name=name), self.assertRaises(SuspiciousFileOperation):
                signed_media_url(name)
        self.assertIn("/private/dev/galleries/1/2/originals/photo.jpg?",
                      signed_media_url("galleries/1/2/originals/photo.jpg"))

    def test_legacy_and_cover_paths(self):
        for name in ("galleries/1/2/legacy.jpg",
                     "galleries/covers-v2/2/variants/preview/cover.webp"):
            self.assertEqual(validate_gallery_object_key("private/dev/" + name),
                             "private/dev/" + name)
            self.assertIn("/private/dev/" + name + "?", signed_media_url(name))

    def test_cleanup_blocks_foreign_keys(self):
        from types import SimpleNamespace
        from . import storage_cleanup, tasks
        key = "private/prod/galleries/1/2/originals/photo.jpg"
        deletion = SimpleNamespace(storage_backend="b2", object_key=key,
                                   attempts=0, save=lambda **kwargs: None)
        with patch.object(storage_cleanup.GalleryStorageDeletion, "objects") as manager, \
                patch.object(storage_cleanup, "delete_b2_object") as delete:
            manager.filter.return_value.order_by.return_value.__getitem__.return_value = [deletion]
            manager.filter.return_value.count.return_value = 0
            self.assertEqual(storage_cleanup.process_storage_deletions()["failed"], 1)
            delete.assert_not_called()
        session = SimpleNamespace(pk=1, object_key=key, upload_id="test")
        with patch.object(tasks.GalleryMultipartUpload, "objects") as manager, \
                patch.object(tasks, "abort_multipart") as abort:
            manager.filter.return_value.order_by.return_value.iterator.return_value = iter([session])
            self.assertEqual(tasks.cleanup_stale_multipart_uploads(),
                             {"aborted": 0, "failed": 1})
            abort.assert_not_called()
